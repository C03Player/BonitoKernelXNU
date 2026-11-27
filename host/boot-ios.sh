#!/bin/sh
# Boot the phone straight into the hosted iOS, from fastboot, without flashing anything: host/boot-ios.sh [MINUTES] [KERNEL]
# The phone returns to the bootloader after MINUTES (default 60), or at once with the power button held. About 90 s to the lock screen.
# Changes made in iOS are saved on the phone, in a save area behind the iOS volume (host/initramfs/xnu-save); the volume itself stays as it
# is. SAVE=0 host/boot-ios.sh: nothing is written, changes are gone at the next boot. SAVE=reset: the saved changes are thrown away first.
# KERNEL: kernel.development.sweet of a hosted CI run (default work/host/kernel.hosted).
set -e
cd "$(dirname "$0")/.."
M=${1:-60}
K=${2:-work/host/kernel.hosted}
[ -s "$K" ] || { echo "no kernel at $K (download one: gh run download RUN -n xnu-kernel)"; exit 1; }
case "${SAVE:-1}" in
0) W= ;;
reset) W="xnusave xnusavereset" ;;
*) W=xnusave ;;
esac
HOSTED_KERNEL=$K host/mkboot.sh work/host/linux-ios.img "xnuauto $W reboot=$((M * 60))" > /dev/null
echo "waiting for the phone in fastboot (hold volume down while it restarts)"
fastboot set_active a
fastboot boot work/host/linux-ios.img
echo "booting; back to the bootloader in $M minutes"
