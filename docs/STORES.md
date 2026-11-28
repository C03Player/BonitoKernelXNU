# Sileo and Zebra (2026-11-28)

Both open on the hosted system in a test copy (RAM only): Sileo lists the installed packages and runs `dpkg`; Zebra starts and tries to
load its sources (offline in the test: no Wi-Fi was joined). **Not verified:** installing a package from a repository (needs Wi-Fi). The
saved changes were not touched.

Packages run as root with signature checks off: they can read everything on the system, including saved passwords. Use trusted sources.

## Test install (RAM)

    host/stores/make-payload.sh work/stores          # downloads from the publishers
    # phone booted into the host Linux (test image), bridge: usbbridge.py serve 2323:23 9999:9999
    gcc -static -O2 -s -o work/stores/hfsreplay host/hfsreplay.c
    echo 'exit 1' > work/stores/stop.sh
    for f in payload.tar hfsreplay stop.sh; do host/stores/send.py work/stores/$f /tmp/$f; done
    host/stores/send.py host/stores/install.sh /tmp/install.sh
    host/psh.py 'XNU_PRESTART=/tmp/stop.sh xnu-run; sh /tmp/install.sh'
    host/psh.py 'xnu-run && xnu-net'

If `xnu.ko` then fails with "Cannot allocate memory", drop caches and compact memory again, or start with `XNU_RAM=1088`.

## What did not work

- Running the bootstrap's setup inside iOS: a job in `/System/Library/LaunchDaemons` starts (editing `launchd.plist` does nothing, see
  below), but some of its programs froze and never returned (`firmware`, `sleep`, once `cat`); cause not proven.
- `/System/Library/xpc/launchd.plist` is ignored: with `rd=md0` launchd runs in its ramdisk mode, skips `launchd_cache_loader` and reads
  the per-service files.
