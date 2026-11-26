# Hosted XNU port (iOS 16 xnu-8796 inside Linux): state

## Done (2026-11-26)
- Gate 1 passed (docs/GATE1.md).
- CI pipeline works in this repository: run 45838983816 built the unmodified direct-port kernel (9 min 38 s). Artifacts in `/usb/work/xnulinux/ci-base/`.
- **Base for the port: xnulinux `cf3399e` (2026-11-25), not its head.** The next commit (`9a92b5f`) adds unprivileged ("pure EL0") hosting, which this
  phone does not need and which grew the machine-layer patch from about 2,460 to 12,400 lines. Against our tree: head rejects 255 hunks, `cf3399e` rejects 111.
  Checkout: `/usb/work/xnulinux/snap` (git worktree of `/usb/work/xnulinux/full`).
- `cf3399e`'s `fki.ko` and `xnu.ko` compile against the host kernel 7.3.5-sdm670-xnuhost (`work/gate2/`). Not loaded on the phone yet.
- Port tree `/usb/work/xnulinux/hosted-8796`: tag `ios-base` = xnu-8796.141.3 + our series (204 of 206 patch files; 0031 and 0041 need the HFS sources
  that `xnu/patches/0026-stage-hfs.sh` stages in CI). Branch `linux64-snap` = `cf3399e`'s patches, rejects merged with `wiggle`, `linux64*.h` copied to
  `EXTERNAL_HEADERS/linux64/`. Original rejects: `/usb/work/xnulinux/rej/`.

## Next
1. Resolve the conflict markers: **25 files, 62 blocks** (`/usb/work/xnulinux/snap-conflicts.txt`; most: `locore.s` 16, `prng_random.c` 14).
   The conflicts seen so far are differences in surrounding code between xnu-12377 and xnu-8796: keep our code, apply the change's intent. The 20 files
   merged without markers still need review. Also apply `xnu-patches/corecrypto/` (the replacement crypto sources, see `scripts/vm-xnu-rebuild.sh`).
2. Add a hosted variant to `.github/workflows/xnu.yml` (LINUX64 machine config, no PAC) and iterate on compile errors.
3. `xnu.ko` for iOS 16 (kernel image loading, device tree, boot args, trust cache), then the kexts (disk, display, input).
4. Memory: the XNU carve-out is limited by `rmtfs-mem` (docs/GATE1.md).
