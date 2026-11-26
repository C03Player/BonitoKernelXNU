#!/bin/bash
# One hosted-kernel test boot: reboot the phone to the bootloader if the test image is running, boot IMAGE (never flashed), stream the kernel log, run xnu-run.
#   host/hosted-test.sh LOGNAME [IMAGE] [xnu-run args...]     log: logs/LOGNAME.log. The image's own timer and watchdog bring the phone back.
cd "$(dirname "$0")/.." || exit 2
NAME=${1:?usage: hosted-test.sh LOGNAME [IMAGE] [xnu-run args]}; IMG=${2:-work/host/linux-hosted.img}; shift; [ $# -gt 0 ] && shift
up() { grep -qs "Sweet Linux" /sys/bus/usb/devices/*/product; }
fb() { timeout 5 fastboot devices | grep -q fastboot; }
bridge() { pkill -f '^python3 -I bonito/tools/usbbridge' ; sleep 1; setsid nohup python3 -I bonito/tools/usbbridge.py serve 2323:23 > logs/bridge.log 2>&1 < /dev/null & sleep 3; }
if up; then bridge; PSH_TIMEOUT=5 timeout 10 host/psh.py 'rebootto bootloader' >/dev/null 2>&1; fi
for i in $(seq 1 130); do fb && break; sleep 2; done
fb || { echo "phone not in the bootloader"; exit 1; }
timeout 20 fastboot set_active a >/dev/null 2>&1
timeout 120 fastboot boot "$IMG" 2>&1 | tail -1
for i in $(seq 1 60); do up && break; sleep 1; done
up || { echo "the Linux gadget did not appear"; exit 1; }
sleep 22; bridge
setsid nohup python3 -I host/klog.py "logs/$NAME.log" 100 >/dev/null 2>&1 < /dev/null &
sleep 3
PSH_TIMEOUT=15 timeout 20 host/psh.py "xnu-run $*"
sleep 25
echo "--- log: $(wc -l < logs/$NAME.log) lines"
grep -a -E 'fki|xnu|XNU|linux64|panic|Oops|BUG:|Unable to handle|lockup|Internal error' "logs/$NAME.log" | cut -d';' -f2- | cut -c1-200 | head -${LINES_SHOWN:-90}
echo "--- phone: $(PSH_TIMEOUT=8 timeout 12 host/psh.py 'cat /proc/uptime; cat /tmp/xnu-insmod.log' 2>&1 | tail -n 3 | tr '\n' ' ')"
