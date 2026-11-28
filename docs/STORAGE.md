# Storage (hosted)

The iOS volume is the direct port's HFS+ volume (16 GiB) at the start of the `userdata` partition (about 50 GiB). The direct port mounted
it read-write; the hosted system never writes it. `xnu-run` gives XNU a device-mapper stack:

    partition (iosbase, read-only) -> iosroot: snapshot in RAM, holds the patches to iOS's code (docs/IOS-PATCHES.md)
                                   -> iossaved: persistent snapshot in the save area

- `host/boot-ios.sh` saves changes (boot-arg `xnusave`). `SAVE=0 host/boot-ios.sh` writes nothing to the phone, as `xnu-run` alone does;
  `SAVE=reset` throws the saved changes away.
- The save area is 8 GiB starting 20 GiB into the partition: behind the volume, clear of the last 4 MiB that the direct port's log uses.
  `xnu-save check` refuses if the volume or the partition does not leave that room.
- The area's first MiB holds a mark with a hash of the volume's header. If the direct port (or anything else) writes the volume, the saved
  changes no longer fit it: they are then neither used nor added to until `SAVE=reset`.
- Linux writes its cache out every 3 seconds. A forced power-off can lose the last moments, and write ordering is not kept as a real disk
  would keep it: if iOS stops booting from the saved changes, `SAVE=reset`.
- When the area fills up, the snapshot stops working; `xnu-run` prints how much is used (a first boot used about 100 MiB).

Verified 2026-11-27: Light appearance set in Settings was still set after a reboot without `sync`; `SAVE=reset` brought back the stored
Dark setting; the volume header's hash was the same on every boot. Not verified: whether the keychain (Wi-Fi passwords) can be read back
after a reboot (the key store is a software stand-in), long use, a full save area.

## Shut down and restart from iOS

`host/initramfs/xnu-halt` follows the kernel log: iOS's shut down powers the phone off, its restart goes to the bootloader. Without it
the phone stayed on with Linux unresponsive (seen 2026-11-27). Tested 2026-11-27 with the phone on USB: it left USB 19 s after
the slider (iOS had unmounted its disk), then appeared again 20 s later, apparently because it is powered: the bootloader starts slot A
(the recovery), whose timer goes to the bootloader. Not tested unplugged. Restart was not tested.

## Adding files to the iOS disk (tests, 2026-11-28)

Before XNU starts (`XNU_PRESTART=script xnu-run`, or after a failed start, on the existing `/dev/mapper/iosroot`):

1. `hfsreplay /dev/mapper/iosroot` (host/hfsreplay.c): the volume's journal holds changes that Linux would ignore.
2. Set bit 8 of the volume header's attributes (byte 1030, "cleanly unmounted"), or Linux mounts it read-only.
3. Mount a 33554432-sector dm linear of it with `-t hfsplus -o rw,force`, copy, unmount, remove the mapping.

Tried in the snapshot in RAM only: Zebra 1.1.37 and Sileo 2.5.1 copied to /Applications (their app list database removed so iOS rebuilds
it) both appeared; Zebra opens in its demo mode (no right to install: no package tools), Sileo aborts for a missing libzstd. After the
copy, `xnu.ko` could not get its memory until `XNU_RAM=1216`. Not tried on the saved changes.

Package tools (2026-11-28, test copy in RAM only): the Procursus rootless bootstrap (`bootstrap-iphoneos-arm64.tar.zst`, suite 1900)
unpacked to `/private/var/jb` the same way, plus a RunAtLoad job in `/System/Library/xpc/launchd.plist` to run `prep_bootstrap.sh`,
`dpkg -i` and `uicache`. **The job never ran**: no `exec dash`, and a `sweettrace=var/jb,xpc/launchd` boot showed only launchd opening
the plist once, nothing under `/var/jb`. No hosted log shows the direct port's `dropbear` job starting either (not verified another way).
Next: log failed posix_spawn calls in the hosted kernel. `/private/var/jb` and the apps are not on the saved changes.
