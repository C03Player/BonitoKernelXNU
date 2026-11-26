# BonitoKernelXNU

An experiment: run the iOS 16 kernel (XNU, xnu-8796.141.3) **inside Linux** on a Google Pixel 3a XL ("bonito": Snapdragon 670, Adreno 615, 4 GB),
so that Linux drivers own the phone's hardware. The method follows [xnulinux](https://github.com/AFK-surf/xnulinux): two kernel modules,
`fki.ko` and `xnu.ko`, load XNU into a running arm64 Linux kernel.

This is a research project. **It does not run iOS on the phone yet.**

## Status (2026-11-26)

| Step | State |
| --- | --- |
| Mainline Linux 7.3.5 host on the phone: USB network and shell, display, GPU driver | works ([docs/GATE1.md](docs/GATE1.md)) |
| Hosted XNU kernel builds in CI | works |
| Hosted XNU starts inside Linux | reaches startup phase 4 and prints its console; further bring-up in progress |
| Disk, display, input, network for the hosted system | not started |
| iOS userland | not started on this path |

Details, test history and next steps: [docs/PORT-HOSTED.md](docs/PORT-HOSTED.md). Why this approach, with measured compatibility: [docs/XNULINUX-EVAL.md](docs/XNULINUX-EVAL.md).

An earlier port that runs XNU directly on the same phone's hardware is at [C03Player/ios-bonito](https://github.com/C03Player/ios-bonito);
its patches and notes are the base of this one.

## Layout

| Path | Contents |
| --- | --- |
| `xnu/patches/` | XNU patch series of the direct port |
| `xnu/linux64/` | the patch that makes that tree run hosted (applied last), and a record of the manual porting edits |
| `hosted/` | `fki.ko` and `xnu.ko`, adapted to this kernel |
| `host/` | Linux host kernel config and build, test boot image, test scripts |
| `bonito/` | phone tools (USB network bridge and others), boot shim and iOS userland pieces of the direct port |
| `docs/` | notes; several describe the direct port |

## Building

You need an arm64 Linux machine for the host side. Paths such as `/usb/work/...` are defaults of the author's machine; override them with the variables named in each script.

1. **Hosted XNU** (GitHub Actions, macOS runner): `gh workflow run xnu.yml -f hosted=true`, then download the `xnu-kernel` artifact.
2. **Linux host kernel:** unpack [sdm670-mainline](https://gitlab.com/sdm670-mainline/linux) tag `sdm670-v7.3.5_beta2`, then `SRC=... OUT=... host/build-mainline.sh`.
3. **Modules:** `make -C $OUT M=$PWD/hosted/fki-ko modules`, then
   `make -C $OUT M=$PWD/hosted/xnu-ko KBUILD_EXTRA_SYMBOLS=$PWD/hosted/fki-ko/Module.symvers modules`.
4. **Test image:** `HOSTED_KERNEL=path/to/kernel.development.sweet host/mkboot.sh work/host/linux-hosted.img "reboot=180"`.
   It also needs files that are not in this repository: AOSP `mkbootimg` and `avbtool` under `downloads/`, and the phone's own GPU firmware (`GPUFW=`).
5. **Run:** with the phone in the bootloader, `host/hosted-test.sh NAME`. The log lands in `logs/NAME.log`.

## Safety

- Use at your own risk. You need an unlocked bootloader.
- The tests use `fastboot boot`: nothing is flashed. They do switch the active slot to `a`.
- The test image reboots to the bootloader on a timer and arms the SoC watchdog. A hang early in the Linux boot still needs the power button.
- The test image opens a shell without a password on the USB network link.

## Licences and credits

No Apple, Google or Qualcomm binaries or firmware are included.

- XNU patches modify Apple's XNU, under the [Apple Public Source License 2.0](https://opensource.apple.com/license/apsl).
- `hosted/` and the hosting patch derive from [AFK-surf/xnulinux](https://github.com/AFK-surf/xnulinux) (`cf3399e`): APSL-2.0 and GPL-2.0, as marked per file.
- The direct port builds on ios-sweet, ios-flame and other projects: see [ATTRIBUTION.md](ATTRIBUTION.md).
