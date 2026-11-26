#!/bin/bash
# Gate-1 boot image from the built host kernel: host/mkboot.sh [OUT.img] ["extra cmdline"]
# Header v0, Image.gz + appended bonito (Samsung panel) dtb, as postmarketOS boots this phone; for `fastboot boot` only (nothing is flashed).
set -euo pipefail
cd "$(dirname "$0")/.."
SRC=${SRC:-/usb/work/linux/src}
K=${OUT:-/usb/work/linux/out}
IMG=${1:-work/host/linux-gate1.img}
EXTRA=${2:-}
DTB=$K/arch/arm64/boot/dts/qcom/${DTBNAME:-sdm670-google-bonito-sdc}.dtb
W=work/host
R=$W/root
rm -rf "$R"
mkdir -p "$R"/{bin,proc,sys,dev,etc} "$(dirname "$IMG")"
cp "$(command -v busybox)" "$R/bin/busybox"
ln -s busybox "$R/bin/sh"
install -m755 host/initramfs/init "$R/init"
install -m755 host/initramfs/report "$R/bin/report"
gcc -static -Os -s -o "$R/bin/rebootto" host/rebootto.c
gcc -static -O2 -s -o "$R/bin/fbcopy" host/fbcopy.c
gcc -static -O2 -s -o "$R/bin/evrelay" host/evrelay.c
make -s -C "$SRC" O="$K" ARCH=arm64 INSTALL_MOD_PATH="$PWD/$R" INSTALL_MOD_STRIP=1 modules_install >/dev/null
# drop module trees that gate 1 does not need, to fit the 64 MiB boot partition
for d in sound drivers/media/{usb,pci,i2c,platform,dvb-frontends,tuners} drivers/infiniband drivers/net/ethernet drivers/staging fs/xfs fs/btrfs fs/nfs fs/smb; do rm -rf "$R"/lib/modules/*/kernel/$d; done
depmod -b "$R" "$(ls "$R/lib/modules")"
# GPU firmware from the phone's vendor image (local only, never committed); paths as in the mainline device tree
G=${GPUFW:-/usb/work/gpufw}
F=$R/lib/firmware/qcom
mkdir -p "$F/sdm670/sargo"
cp "$G/a630_sqe.fw" "$G/a630_gmu.bin" "$F/"
cp "$G/a615_zap.elf" "$F/sdm670/sargo/a615_zap.mbn"
# GPU test userland (host/gpu-userland.py), when it has been assembled
[ -d $W/gpu ] && cp -a $W/gpu "$R/gpu"
# hosted XNU: the two modules (built in hosted/) and the kernel image (HOSTED_KERNEL=path of kernel.development.sweet from a hosted CI run)
if [ -n "${HOSTED_KERNEL:-}" ]; then
	mkdir -p "$R/hosted" "$R/lib/firmware/xnu"
	cp hosted/fki-ko/fki.ko hosted/xnu-ko/xnu.ko "$R/hosted/"
	cp "$HOSTED_KERNEL" "$R/lib/firmware/xnu/kernel.macho"
	install -m755 host/initramfs/xnu-run "$R/bin/xnu-run"
	# dmsetup (this machine's, with its libraries) for the writable snapshot of the root disk
	mkdir -p "$R/dm"
	D=$(command -v dmsetup)
	cp -L "$D" $(ldd "$D" | grep -oE '/[^ )]+') "$R/dm/"
	python3 host/mkadtprops.py "$R/lib/firmware/xnu/adtprops.bin"
fi
(cd "$R" && find . | cpio -o -H newc --quiet --owner=0:0 | gzip -9) > $W/initramfs.gz
# the mainline SDM670 tree has no watchdog node; add the SoC's APSS watchdog (stock device tree address, as SDM845's mainline node) to a copy
cp "$DTB" $W/board.dtb
N=/soc@0/watchdog@17980000
fdtput -c $W/board.dtb $N
fdtput -t s $W/board.dtb $N compatible qcom,apss-wdt-sdm845 qcom,kpss-wdt
fdtput -t x $W/board.dtb $N reg 0 17980000 0 1000
fdtput -t x $W/board.dtb $N clocks "$(fdtget -t x $W/board.dtb /clocks/sleep-clk phandle)"
fdtput -t u $W/board.dtb $N interrupts 0 0 1
cat "$K/arch/arm64/boot/Image.gz" $W/board.dtb > $W/Image.gz-dtb
ls -l $W/Image.gz-dtb $W/initramfs.gz
PYTHONPATH=downloads/mkbootimg python3 downloads/mkbootimg/mkbootimg.py --header_version 0 --kernel $W/Image.gz-dtb --ramdisk $W/initramfs.gz \
	--base 0 --kernel_offset 0x8000 --ramdisk_offset 0x1000000 --tags_offset 0x100 --pagesize 4096 \
	--cmdline "console=tty0 panic=10 softlockup_panic=1 ${HOSTED_KERNEL:+cma=1700M@0x100000000} reboot=240 epoch=$(date +%s) $EXTRA" -o "$IMG"
python3 downloads/avb/avbtool.py add_hash_footer --image "$IMG" --partition_size 67108864 --partition_name boot
ls -l "$IMG"
