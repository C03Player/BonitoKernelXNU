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
echo "root:x:0:0:root:/:/bin/sh" > "$R/etc/passwd"
echo "root:x:0:" > "$R/etc/group"
ln -s busybox "$R/bin/sh"
install -m755 host/initramfs/init "$R/init"
install -m755 host/initramfs/report "$R/bin/report"
gcc -static -Os -s -o "$R/bin/rebootto" host/rebootto.c
gcc -static -O2 -s -o "$R/bin/fbcopy" host/fbcopy.c
gcc -static -O2 -s -o "$R/bin/evrelay" host/evrelay.c
gcc -static -O2 -s -I"${KHDR:-/usb/work/linux/hdr/include}" -o "$R/bin/kmsfb" host/kmsfb.c
gcc -static -O2 -s -I"${KHDR:-/usb/work/linux/hdr/include}" -o "$R/bin/adrenod" host/gpu/adrenod.c
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
# Wi-Fi on the host (host/initramfs/wifi-up): the modem helpers and tools from Debian packages unpacked under WIFIUSER/root,
# the driver firmware in WIFIUSER/fw, and the WLAN firmware from the phone's own images (local only, never committed)
WU=${WIFIUSER:-/usb/work/linux/wifi-userland}
MF=${MODEMFW:-/usb/work/modem/fw}
if [ -d "$WU/root" ] && [ -f "$MF/wlanmdsp.mbn" ]; then
	install -m755 host/initramfs/wifi-up "$R/bin/wifi-up"
	install -m755 host/initramfs/wifi-join "$R/bin/wifi-join"
	install -m755 host/initramfs/udhcpc.sh "$R/etc/udhcpc.sh"
	install -m755 host/initramfs/xnu-net "$R/bin/xnu-net"
	cp "$WU/root/usr/sbin/dnsmasq" "$WU/root/usr/sbin/nft" "$R/bin/"
	L=$R/lib/aarch64-linux-gnu
	mkdir -p "$L" "$R/lib/firmware/ath10k/WCN3990/hw1.0"
	for b in usr/bin/rmtfs usr/bin/tqftpserv sbin/iw sbin/wpa_supplicant usr/bin/wpa_passphrase; do cp "$WU/root/$b" "$R/bin/"; done
	# the libraries they need, from the unpacked packages first and this machine otherwise
	for i in 1 2 3 4 5 6 7 8; do
		for n in $(objdump -p "$R"/bin/{rmtfs,tqftpserv,iw,wpa_supplicant,dnsmasq,nft} "$L"/* 2>/dev/null | awk '/NEEDED/ {print $2}' | sort -u); do
			[ -e "$L/$n" ] && continue
			src=$(find "$WU/root" /lib/aarch64-linux-gnu /usr/lib/aarch64-linux-gnu -name "$n" 2>/dev/null | head -n 1)
			[ -n "$src" ] || { echo "no library $n"; exit 1; }
			cp -L "$src" "$L/$n"
		done
	done
	cp "$L/ld-linux-aarch64.so.1" "$R/lib/ld-linux-aarch64.so.1"
	cp "$WU/root/lib/firmware/regulatory.db-upstream" "$R/lib/firmware/regulatory.db"
	cp "$WU/root/lib/firmware/regulatory.db.p7s-upstream" "$R/lib/firmware/regulatory.db.p7s"
	cp "$WU/fw/firmware-5.bin" "$R/lib/firmware/ath10k/WCN3990/hw1.0/"
	cp "$MF/bdwlan-bonito.bin" "$R/lib/firmware/ath10k/WCN3990/hw1.0/board.bin"
	mkdir -p "$F/sdm670/sargo"
	cp "$MF/wlanmdsp.mbn" "$F/sdm670/sargo/"
fi
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
	--cmdline "console=tty0 panic=10 softlockup_panic=1 ${HOSTED_KERNEL:+cma=1920M@0x100000000} reboot=240 epoch=$(date +%s) $EXTRA" -o "$IMG"
python3 downloads/avb/avbtool.py add_hash_footer --image "$IMG" --partition_size 67108864 --partition_name boot
ls -l "$IMG"
