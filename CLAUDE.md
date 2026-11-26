# BonitoKernelXNU

Goal: make iOS 16.7 (iPhone X userland, `iPhone10,3` IPSW) usable on a Pixel 3a XL ("bonito", SDM670, Adreno 615, 4 GB) by hosting XNU inside a Linux kernel
(the approach of https://github.com/AFK-surf/xnulinux: `xnu.ko` + `fki.ko`) so Linux owns the hardware, instead of driving every device from XNU.
Start with `docs/XNULINUX-EVAL.md` (measured compatibility, verdict, gated plan), then `docs/SHELL.md`, `docs/STANDALONE.md`, `docs/GPU.md`, `docs/PERF.md`.

## The fallback: the direct port (do not change it from here)
`reference-ios-direct-port` -> `/workspace/IOSOnPixel`: the working project where XNU runs directly on the hardware (iOS boots to the home screen; GPU via Turnip + SweetMetal2 at ~15 fps; no Wi-Fi;
root shell over the USB gadget works; 205 XNU patches in `xnu/patches`; CI workflows; logs/work/images). Read it freely, keep it intact, and build new work here.
Copied here: all its tracked files (`bonito/` tools, shim, userland; `xnu/patches`; `.github/` workflows; `docs/`) plus build inputs (`downloads/mkbootimg`, `downloads/avb`, `stock/unpacked/dtb`, the kernel of CI run 45423074766 in `work/`). `bonito/tools/mkios.sh` builds images here. Older logs and images stay in the old project.

## Priorities (2026-11-26)
Open problems of the direct port: ~15 fps (also in Settings), wallpapers need a HEIC->PNG conversion (no HEVC decoder), no internet. Judge every plan by which of these it fixes
(hosting fixes breadth: Wi-Fi/modem/audio/power; it does NOT change the GPU workload; GPU numbers on Linux vs the port: docs/GATE1.md).
Prefer research over slow phone tests; work autonomously until it is done; tell the user plainly what was verified and what was inferred.

## Hard rules
- Never risk fastboot: no GPT edits, no firmware partition writes (xbl, abl, tz, hyp, aop, keymaster, devcfg, modem...), never touch slot A's contents. Only `fastboot flash boot_b/dtbo_b/vbmeta_b`, `set_active`, `boot`, `reboot`.
- Ask before booting the phone in ways the user did not ask for. A standalone slot-B boot once left the phone stuck (no timer): PC-driven `fastboot boot` images with `sweetreboot=SECS` reset themselves and are the safe test method.
- The phone must be plugged in for any phone step; if it is not, do research.

## Where things are (this machine: Raspberry Pi 5 host, rootless dev container)
- `/usb/work/`: `xnulinux/` (upstream clone, xnu-8796 source and a patch-trial copy), `standalone/` (known-good boot image, slot B backups, plugin and wallpaper backups), `dyld/`, `modem/`, `shell/` (ssh key, built binaries), `android-probe/`.
- `xnulinux/` here: a copy of the upstream repo; `third_party/lineage-kernel-msm-4.9` (4.9.337) and `lineage-device-bonito` (branch lineage-23.0).
- Host kernel candidates: Lineage msm-4.9 (what the recovery runs; needs KPROBES=y, SW_TTBR0_PAN=n, nokaslr, KPTI off, small shims) or sdm670-mainline (gitlab.com/sdm670-mainline/linux, tags to 7.3.5).
- GitHub: C03Player/ios-bonito (the direct port, CI builds XNU and userland; dispatch workflows by hand: push runs get cancelled in the queue). This repo: C03Player/BonitoKernelXNU (**public**: commit no serial numbers, firmware, keys or personal notes); workflows run by hand only.
- Gotchas: kernel command line is 591 chars (extra args are dropped silently); the dev container has no net privileges (use `bonito/tools/usbbridge.py`); `/workspace` is nearly full (clear only your own scratch; images/logs in the old project are big); recovery in slot A has a 240 s reboot timer.

## Next step (gate 1, needs the phone)
Boot each host kernel on the phone with `fastboot boot` (no flashing) and check: panel variant, USB networking, modules/kprobes/CMA, a ~3 GB reserved-memory carve-out, `kpti` state, GPU (run the same `vktest` bandwidth test as on iOS), Wi-Fi/modem.
Then gate 2: build `fki.ko`/`xnu.ko` against it and boot hosted XNU on the Kryo cores; gate 3: port the machine layer (297 of 541 hunks reject on xnu-8796) and our iOS patches.
Phone state at hand-over is unknown (it was unplugged): check `fastboot getvar current-slot`; slot B was armed with 2 standalone boots left.
