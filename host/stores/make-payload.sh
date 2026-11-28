#!/bin/sh
# make-payload.sh DIR: download the Procursus rootless bootstrap, Sileo and Zebra from their publishers and pack them into DIR/payload.tar
# for install.sh. Nothing downloaded is committed.
set -e
D=${1:?usage: make-payload.sh DIR}; mkdir -p "$D/dl" "$D/x" "$D/pay/inst/Applications"
cd "$D/dl"
[ -s bootstrap.tar.zst ] || curl -sSf -m 600 -o bootstrap.tar.zst https://apt.procurs.us/bootstraps/1900/bootstrap-iphoneos-arm64.tar.zst
[ -s sileo.deb ] || curl -sSfL -m 600 -o sileo.deb https://github.com/Sileo/Sileo/releases/download/2.5.1/org.coolstar.sileo_2.5.1_iphoneos-arm64.deb
[ -s zebra.deb ] || curl -sSfL -m 600 -o zebra.deb https://github.com/zbrateam/Zebra/releases/download/v1.1.37/xyz.willy.zebra_1.1.37_iphoneos-arm64.deb
sha256sum bootstrap.tar.zst sileo.deb zebra.deb
cd ..
zstd -dqc dl/bootstrap.tar.zst | gzip -9 > pay/bootstrap.tar.gz
# dpkg's records: the stores, and "firmware" (the bootstrap's own program for it froze on the phone)
printf 'Package: firmware\nEssential: yes\nStatus: install ok installed\nPriority: required\nSection: System\nMaintainer: local\nArchitecture: iphoneos-arm64\nVersion: 16.7\nDescription: this iOS version\n\n' > pay/inst/status.add
for p in sileo zebra; do
	rm -rf "x/$p"; dpkg-deb -R "dl/$p.deb" "x/$p"
	cp -a "x/$p/var/jb/Applications/"*.app pay/inst/Applications/
	{ sed -n 1p "x/$p/DEBIAN/control"; echo 'Status: install ok installed'; sed 1d "x/$p/DEBIAN/control" | sed '/^$/d'; echo; } >> pay/inst/status.add
done
tar -C pay -cf payload.tar .
ls -l payload.tar
