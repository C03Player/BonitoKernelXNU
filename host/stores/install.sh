#!/bin/sh
# install.sh [ROOTDEV]: ON THE PHONE, with /tmp/payload.tar (make-payload.sh) and /tmp/hfsreplay there, before XNU starts: put the package
# tools in /private/var/jb and Sileo and Zebra in /Applications of the iOS volume on ROOTDEV (default: the snapshot in RAM,
# /dev/mapper/iosroot, made by `XNU_PRESTART=/tmp/stop.sh xnu-run` where stop.sh is "exit 1"; docs/STORES.md).
# Writing to the saved changes (/dev/mapper/iossaved) changes what the user keeps: only on their say-so.
set -e
D=${1:-/dev/mapper/iosroot}; DM="/dm/ld-linux-aarch64.so.1 --library-path /dm /dm/dmsetup"; V=/mnt/app
chmod 755 /tmp/hfsreplay; /tmp/hfsreplay "$D"
a=$(dd if="$D" bs=1 skip=1030 count=1 2>/dev/null | od -An -tu1 | tr -d ' ')
printf "\\$(printf '%03o' $((a | 1)))" | dd of="$D" bs=1 seek=1030 conv=notrunc 2>/dev/null
DM_DISABLE_UDEV=1 $DM create appvol --noudevsync --table "0 33554432 linear $D 0"
modprobe -q hfsplus; modprobe -q nls_utf8
mkdir -p $V; mount -t hfsplus -o rw,force /dev/mapper/appvol $V
grep -q " $V hfsplus rw" /proc/mounts
[ ! -e $V/private/var/jb ] || { echo "/var/jb exists already: nothing done"; umount $V; $DM remove appvol; exit 1; }
rm -rf /tmp/pay; mkdir /tmp/pay; tar -C /tmp/pay -xf /tmp/payload.tar; rm /tmp/payload.tar
gzip -dc /tmp/pay/bootstrap.tar.gz | (cd $V/private && tar -xf - ./var/jb)
cp -a /tmp/pay/inst/Applications/Sileo.app /tmp/pay/inst/Applications/Zebra.app $V/Applications/
chown -R 0:0 $V/Applications/Sileo.app $V/Applications/Zebra.app
chmod 755 $V/Applications/Sileo.app/Sileo $V/Applications/Zebra.app/Zebra
chmod 4755 $V/Applications/Sileo.app/giveMeRoot	# Sileo's helper that installs packages as root
cat /tmp/pay/inst/status.add >> $V/private/var/jb/Library/dpkg/status
# iOS rebuilds its list of apps when the database is gone
find $V/private/var -name "com.apple.LaunchServices*.csstore" -exec rm {} +
sync; umount $V; DM_DISABLE_UDEV=1 $DM remove --noudevsync appvol
rm -rf /tmp/pay; sync; echo 3 > /proc/sys/vm/drop_caches; echo 1 > /proc/sys/vm/compact_memory
echo "install ok"
