#!/bin/sh
# stockapps.sh ROOTDEV: ON THE PHONE, before XNU starts, with /tmp/hfsreplay there: move iOS's own staged apps (Calculator, Clock, Notes,
# Calendar, ... in /private/var/staged_system_apps) to /Applications. A real device installs them at first boot; this system boots as a
# restore does and never gets to it. Renames only: next to nothing is written. Test it on the snapshot in RAM
# (XNU_PRESTART=/tmp/stockapps.sh xnu-run); writing to the saved changes (/dev/mapper/iossaved) changes what the user keeps: only on
# their say-so (docs/STORES.md).
set -e
D=${1:?root device}; DM="/dm/ld-linux-aarch64.so.1 --library-path /dm /dm/dmsetup"; V=/mnt/app
chmod 755 /tmp/hfsreplay; /tmp/hfsreplay "$D"
a=$(dd if="$D" bs=1 skip=1030 count=1 2>/dev/null | od -An -tu1 | tr -d ' ')
printf "\\$(printf '%03o' $((a | 1)))" | dd of="$D" bs=1 seek=1030 conv=notrunc 2>/dev/null
DM_DISABLE_UDEV=1 $DM create appvol --noudevsync --table "0 33554432 linear $D 0"
modprobe -q hfsplus; modprobe -q nls_utf8
mkdir -p $V; mount -t hfsplus -o rw,force /dev/mapper/appvol $V
grep -q " $V hfsplus rw" /proc/mounts
n=0
for app in $V/private/var/staged_system_apps/*.app; do
	[ -d "$app" ] || continue
	[ -e "$V/Applications/${app##*/}" ] && continue
	mv "$app" $V/Applications/ && n=$((n + 1))
done
# iOS rebuilds its list of apps when the database is gone
[ $n = 0 ] || find $V/private/var -name "com.apple.LaunchServices*.csstore" -exec rm {} +
sync; umount $V; DM_DISABLE_UDEV=1 $DM remove --noudevsync appvol; sync
echo "$n apps moved to /Applications"
