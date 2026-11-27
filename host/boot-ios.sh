#!/bin/sh
# Boot the phone straight into the hosted iOS, from fastboot, without flashing anything: host/boot-ios.sh [MINUTES] [KERNEL]
# The phone returns to the bootloader after MINUTES (default 60), or at once with the power button held. Nothing on it is changed:
# everything runs from RAM, and iOS's changes are gone at the next boot. About 90 s to the lock screen.
# KERNEL: kernel.development.sweet of a hosted CI run (default work/host/kernel.hosted).
set -e
cd "$(dirname "$0")/.."
M=${1:-60}
K=${2:-work/host/kernel.hosted}
[ -s "$K" ] || { echo "no kernel at $K (download one: gh run download RUN -n xnu-kernel)"; exit 1; }
HOSTED_KERNEL=$K host/mkboot.sh work/host/linux-ios.img "xnuauto reboot=$((M * 60))" > /dev/null
echo "waiting for the phone in fastboot (hold volume down while it restarts)"
fastboot set_active a
fastboot boot work/host/linux-ios.img
echo "booting; back to the bootloader in $M minutes"
