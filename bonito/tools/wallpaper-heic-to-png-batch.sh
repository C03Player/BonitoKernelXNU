#!/bin/bash
# Overnight 2026-11-24 batch that wrote PNG-converted wallpaper images over the HEIC files on the phone (no HEVC decoder in this port).
# Reference copy of that session's batch. Env TODO=file: todo.tsv (PNG<TAB>phone path) made by converting each HEIC from the host root image with ImageMagick's convert.
# See docs/WALLPAPER.md. Run with: bash script (a file without +x silently never starts).
cd "$(dirname "$0")/../.." || exit 2
TODO=${TODO:?set TODO to a todo.tsv}
[ -r "$TODO" ] || { echo "cannot read $TODO"; exit 2; }
K=45029003673; L=/tmp/wpfix5.log; echo "start $(date)" > $L
V="/private/var/mobile/Library/Application Support/PRBPosterExtensionDataStore/59/Extensions/com.apple.WallpaperKit.CollectionsPoster/configurations/75A5625B-8ADD-4671-B9ED-566F12BB3512/versions/0"
fin() { echo "$1" >> $L; echo "WPFIX DONE $(date)" >> $L; exit ${2:-1}; }
OK=0
for try in 1 2 3; do
  bonito/tools/ci-cycle.sh $K fl_wpfix "sweetnoinit=1 sweetreboot=150" 400 "sweetfb_sync" > /tmp/cycle-fl_wpfix.log 2>&1
  grep -a -q "VFS_SYNC(root) = 0" logs/fl_wpfix.txt && { OK=1; break; }
done
[ $OK = 1 ] || fin "journal flush failed" 2
rm -f logs/fl_wpfix.txt logs/fl_wpfix.png bonito/shim/out/fl_wpfix.img work/fl_wpfix.payload
[ "$(fastboot getvar product 2>&1 | grep -a product | head -1 | awk '{print $2}')" = bonito ] || fin "not bonito" 3
fastboot set_active a >/dev/null 2>&1; fastboot reboot >/dev/null 2>&1
for i in $(seq 1 40); do adb devices | grep -q recovery && break; sleep 5; done
adb devices | grep -q recovery || fin "no recovery" 4
adb shell 'setprop ctl.stop sweetreboot; setprop ctl.stop sweetdiag' >/dev/null 2>&1
rep() { exec 4</dev/null; python3 -I bonito/tools/hfsx_write.py adb:/dev/block/mmcblk0p72 replace "$1" "$2" >> /tmp/wpfix5-w.log 2>&1
  for t in 1 2 3; do sleep 3; adb shell 'sync; echo 3 > /proc/sys/vm/drop_caches' </dev/null
    python3 -I bonito/tools/hfsx.py --phone cat "$2" /tmp/rb-wpfix >/dev/null 2>&1
    if cmp -s "$1" /tmp/rb-wpfix; then echo "ok   ${2##*/}" >> $L; rm -f /tmp/rb-wpfix; return 0; fi; done
  echo "FAIL $2" >> $L; rm -f /tmp/rb-wpfix; return 1; }
n=0
while IFS=$'\t' read -r src dst <&3; do
  rep "$src" "$dst" || fin "write failed, stopping before any boot" 5
  n=$((n+1))
done 3< "$TODO"
echo "wrote $n wallpaper images" >> $L
rep /usb/work/standalone/backup-wallpaper/RuntimeSnapshot-home.atx.orig "$V/RuntimeSnapshot-home.atx" || fin "restore of home cache failed" 6
adb shell sync; adb reboot bootloader >/dev/null 2>&1; for i in $(seq 1 40); do timeout 5 fastboot devices | grep -q fastboot && break; sleep 3; done
rm -f logs/wph2*.png
SWIPE=1000 SHOTSECS=20 bonito/tools/seam-sweep.sh $K wph 1 "sweetddr=0" >> $L 2>&1
echo "WPFIX DONE $(date)" >> $L
