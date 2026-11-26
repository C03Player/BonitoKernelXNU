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
- (0002 host devices was added after the fifth phone test.) 0003 boot without iBoot, 0004 macOS 27 system calls, 0005 paravirtual ticket locks, 0008 replacement corecrypto.
- 47-bit user address space and the macOS page-size changes: iOS user addresses fit the stock 39-bit, 4 KB-granule attributes; xnu-8796 already picks 16 KB VM pages above 1 GB of RAM.
- Build base: **the `SWEET` machine config** (it carries the iOS userland support: HFS, pthread, AES, plain `arm64`), with `SWEET_HOSTED` in `SWEET.h`: 4 KB pages, no early framebuffer,
  eMMC log or reset paths. The first try on the `BCM2837` config (run 45844052472) built as arm64e and lacked that support.
- Still to check at run time: other SWEET hardware paths (GIC and IPIs: use `cpus=1` first; drivers matched from the device tree).

## Host modules
`hosted/` = `fki.ko` and `xnu.ko` of cf3399e (APSL-2.0 / GPL-2.0, see their SPDX lines), changed for this port: boot command line 608 bytes, `T0SZ=25` in XNU's world.
Build: `make -C /usb/work/linux/out M=$PWD/hosted/fki-ko modules`, then `xnu-ko` with `KBUILD_EXTRA_SYMBOLS`.
Kernel layout of the hosted build: link address `0xfffffff007004000` (not large memory), 39-bit user and kernel tables.

## Phone tests (`host/hosted-test.sh NAME`: boots the test image without flashing; log in `logs/NAME.log`)
- hosted1: `fki_contig_alloc` out of memory. Fix: `cma=800M` on the host command line.
- hosted2: `fki_enter` read pointer-authentication key registers (undefined on Kryo 360). Fix: guard in `fki_mod.c`.
- **hosted3: XNU 8796 runs inside Linux**: image mapped, `arm_init`, startup phase 4, `kprintf` console, then panic `pe_init_fiq: cannot find GIC node` (fixed: no `HAS_GIC_V3` hosted);
  assert `phys_cluster_id <= MAX_CPU_CLUSTER_PHY_ID` (fixed: no `cluster-type` in the device tree). Linux survived the panic.
- The mainline tree has no watchdog node for SDM670: `host/mkboot.sh` adds the APSS watchdog to its copy of the dtb (verified: `/dev/watchdog` appears and is fed).

- hosted4: VM system initialised (129011 free pages); panic `kmem_range_init ... claim zones`: macOS zone reservation (128 GiB) larger than the 39-bit layout. Fix: iOS sizes.

- **hosted5: the whole Mach bootstrap runs** (VM, zones, scheduler, threads, startup phase 15) and enters IOKit (`PE_init_iokit`); fault in `IONVRAMCHRPHandler::unserializeVariables`
  (blank NVRAM). Fix: apply xnulinux patch 0002 (host devices; also the generic platform expert for an unknown platform).

- hosted6: **the kernel boots through IOKit startup** (SWEET platform services register) and waits for a root disk. A warning about an XNU stack with sp bit 14 set (idle path) remains.
- hosted7: root disk found (`hostdisk=/dev/mmcblk0p72`, read-only, the direct port's iOS image), 1536 MB, 16 KB pages; `cma=1700M@0x100000000`. Panic `write_pte_fast: PTE write is unaligned`
  from the commpage: the slid text page address was 4 KB aligned. Fixed.

## Next
1. CI: `gh workflow run xnu.yml -f hosted=true`; fix compile and link errors (artifact `xnu-log`).
2. Load it with `xnu.ko` on the phone: early boot to console messages. Adapt `xnu.ko` to xnu-8796 where needed.
3. Host devices (0002) and kexts: disk, display, input.
4. Memory: the XNU carve-out is limited by `rmtfs-mem` (docs/GATE1.md).
