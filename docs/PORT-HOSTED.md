# Hosted XNU port (iOS 16 xnu-8796 inside Linux): state

## Done (2026-11-26)
- Gate 1 passed (docs/GATE1.md).
- `fki.ko` and `xnu.ko` (xnulinux b5ff094) compile unchanged against the phone's host kernel 7.3.5-sdm670-xnuhost
  (one warning, `xnu_main.c:376`). Not loaded on the phone: there is no hosted kernel image for them to run.
- Port tree `/usb/work/xnulinux/hosted-8796`: tag `ios-base` = xnu-8796.141.3 + our series (204 of 206 patch files apply;
  0031 and 0041 need the HFS sources that `xnu/patches/0026-stage-hfs.sh` stages in CI). Branch `linux64-port` =
  xnulinux's patches applied with `git apply --reject`; rejects are committed as `.rej` files. Counts: `/usb/work/xnulinux/linux64-apply.txt`.

## Next
1. Resolve the rejects into a LINUX64 machine config for xnu-8796 (no PAC), keeping our userland patches and dropping hardware drivers.
2. Build it. The proven route is the GitHub macOS workflow (`.github/workflows/xnu.yml`); this repository has no remote yet.
3. `xnu.ko` changes for iOS 16 (kernel collection loading, device tree, boot args, trust cache), then the kexts (disk, display, input).
