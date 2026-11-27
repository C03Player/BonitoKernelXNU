# BonitoKernelXNU

BonitoKernelXNU is an experiment in running the iOS 16 kernel (XNU, version xnu-8796.141.3) inside Linux on a Google Pixel 3a XL, codenamed "bonito".
The phone has a Snapdragon 670 processor, an Adreno 615 GPU and 4 GB of memory.

The idea is to let Linux, with its existing drivers, own the phone's hardware, while XNU runs alongside it as a guest that asks Linux for what it needs.
This follows the approach of [xnulinux](https://github.com/AFK-surf/xnulinux), where two Linux kernel modules, `fki.ko` and `xnu.ko`, load XNU into a running arm64 Linux kernel.

**This is not a usable system.** It is research in progress.

## Why host XNU inside Linux?

An earlier port, [C03Player/ios-bonito](https://github.com/C03Player/ios-bonito), runs XNU directly on the same phone. It reaches the iOS home screen,
but every piece of hardware needs a driver written for XNU, which is slow work, and several parts of the phone still do not work there.

A mainline Linux kernel already drives much of this phone. Hosting XNU inside Linux aims to reuse that work. It does not by itself make graphics faster:
the GPU still has to do the same work. The reasoning, and the compatibility measurements behind it, are in [docs/XNULINUX-EVAL.md](docs/XNULINUX-EVAL.md).

## Where things stand (27 November 2026)

**iOS boots to its home screen on the phone, running inside Linux, and draws on the GPU.** The ported XNU kernel, loaded into the running
Linux kernel, starts the iOS 16 system from the phone's storage on four processor cores. About 90 seconds after starting, the lock screen is up.

What works, as seen in screenshots and logs from the phone:

- The lock screen, home screen, App Library, Control Center, Settings and Safari's start page, drawn on the Adreno GPU.
- Touch and the side buttons.
- About 15 frames per second while swiping. The GPU then runs at its highest rated clock for this chip, so that is the limit now.
  A frame counter is drawn in the top-left corner.
- Safari: a test web page served by the phone's Linux side loads and draws.
- The Settings page for Wi-Fi: it lists the networks the phone's radio hears, and joining a test network works.
  Joining a real network with a password, and reaching the internet through it, have not been tested yet.
- The phone's battery level and charging state.

What does not work, or is not there:

- Changes made in iOS are kept in memory only and are lost at reboot. That includes Wi-Fi passwords.
- The phone has to be started from a computer. Nothing is installed on it.
- Sound, the cameras, Bluetooth and the mobile network.
- The on-screen keyboard is sometimes drawn shifted to the right, with its last column cut off.
- The Photos widget stays black, and several iOS background services crash repeatedly.

The notes on each part are in [docs/GPU-BRIDGE.md](docs/GPU-BRIDGE.md) and [docs/NETWORK.md](docs/NETWORK.md).
The history of the port is in [docs/PORT-HOSTED.md](docs/PORT-HOSTED.md).

## Trying it

With the phone in its bootloader and the boot image's parts built (see below), this starts iOS without writing anything to the phone:

```
host/boot-ios.sh 60
```

The number is the minutes after which the phone returns to its bootloader.

## What is in this repository

- `xnu/patches/` holds the XNU patch series from the direct port.
- `xnu/linux64/` holds the additional patch that makes that kernel run inside Linux. It is applied after the series above. A script next to it records the manual porting edits.
- `hosted/` holds the `fki.ko` and `xnu.ko` modules, adapted to this kernel.
- `host/` holds the Linux kernel configuration, the build scripts, the test boot image and the test scripts.
- `bonito/` holds phone tools, including a USB network bridge, together with the boot shim and iOS userland pieces of the direct port.
- `docs/` holds the project notes. Several of them describe the direct port.

## Building and testing

You need an arm64 Linux machine for the host side. Some scripts default to paths such as `/usb/work/`, which exist on the author's machine.
Each script names the variables you can set to use your own locations.

### 1. Build the hosted XNU kernel

Run the GitHub Actions workflow, then download the `xnu-kernel` artifact from the finished run:

```
gh workflow run xnu.yml -f hosted=true
```

### 2. Build the Linux host kernel

Download the [sdm670-mainline](https://gitlab.com/sdm670-mainline/linux) source at tag `sdm670-v7.3.5_beta2`, unpack it, and run:

```
SRC=/path/to/source OUT=/path/to/build host/build-mainline.sh
```

### 3. Build the two kernel modules

```
make -C /path/to/build M=$PWD/hosted/fki-ko modules
make -C /path/to/build M=$PWD/hosted/xnu-ko KBUILD_EXTRA_SYMBOLS=$PWD/hosted/fki-ko/Module.symvers modules
```

### 4. Create the test boot image

```
HOSTED_KERNEL=/path/to/kernel.development.sweet host/mkboot.sh work/host/linux-hosted.img "reboot=180"
```

This step needs some files that are not included here: the AOSP tools `mkbootimg` and `avbtool`, placed under `downloads/`,
and the GPU firmware from your own phone, whose folder you give in the `GPUFW` variable.

### 5. Run a test

Put the phone in its bootloader, then run the following command, replacing `NAME` with a name for the test:

```
host/hosted-test.sh NAME
```

The phone's log is saved to `logs/NAME.log`.

## Safety

Use this project at your own risk. It requires a phone with an unlocked bootloader.

- The tests start the image with `fastboot boot`, so nothing is flashed to the phone. They do change the active slot to `a`.
- The test image returns to the bootloader after a timer expires, and it also uses the processor's hardware watchdog to recover from hangs.
  If Linux itself hangs very early during startup, you will need to hold the power button.
- The test image offers a shell **without a password** on the USB network link. Only use it with a computer you trust.

## Licences and credits

No binaries or firmware from Apple, Google or Qualcomm are included.

- The XNU patches modify Apple's XNU and fall under the [Apple Public Source License 2.0](https://opensource.apple.com/license/apsl).
- The files in `hosted/` and the hosting patch are derived from [AFK-surf/xnulinux](https://github.com/AFK-surf/xnulinux) at commit `cf3399e`.
  They are licensed under APSL 2.0 or GPL 2.0, as marked in each file.
- The direct port builds on ios-sweet, ios-flame and other projects, listed in [ATTRIBUTION.md](ATTRIBUTION.md).
