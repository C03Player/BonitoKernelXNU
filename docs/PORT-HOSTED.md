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

## Resolved (2026-11-26)
`xnu/linux64/9001-linux64-xnu8796.patch` = xnulinux `cf3399e` patches **0001, 0006, 0007** on our tree, every rejected hunk adapted by `xnu/linux64/port-edits.py`
(32 files; machine flag `-mcpu=cortex-a55+crypto` on the BCM2837 base config). Left out on purpose, to be revisited:
- 0002 host devices (needed before any disk, display or input), 0003 boot without iBoot, 0004 macOS 27 system calls, 0005 paravirtual ticket locks, 0008 replacement corecrypto.
- 47-bit user address space and the macOS page-size changes: iOS user addresses fit the stock 39-bit, 4 KB-granule attributes; xnu-8796 already picks 16 KB VM pages above 1 GB of RAM.
- Nothing compiled yet at the time of writing.

## Next
1. CI: `gh workflow run xnu.yml -f hosted=true -f machine_config=BCM2837`; fix compile and link errors (artifact `xnu-log`).
2. Load it with `xnu.ko` on the phone: early boot to console messages. Adapt `xnu.ko` to xnu-8796 where needed.
3. Host devices (0002) and kexts: disk, display, input.
4. Memory: the XNU carve-out is limited by `rmtfs-mem` (docs/GATE1.md).
