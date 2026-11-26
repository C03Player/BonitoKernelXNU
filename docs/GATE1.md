# Gate 1: Linux host kernel on the phone (2026-11-26)

Host: sdm670-mainline `sdm670-v7.3.5_beta2` + `host/mainline-host.config` (`host/build-mainline.sh`, source and build on `/usb/work/linux/`).
Image: `host/mkboot.sh` (initramfs with busybox, modules, GPU firmware) -> `work/host/linux-gate1.img`. Nothing is flashed.

## Run it
```
host/mkboot.sh work/host/linux-gate1.img "reboot=600"
fastboot set_active a && fastboot boot work/host/linux-gate1.img     # USB gadget "Sweet Linux" after about 25 s
python3 -I bonito/tools/usbbridge.py serve 2323:23 &
host/psh.py 'cat /www/report.txt'
```
The phone reboots to the bootloader by itself after `reboot=SECS` (default 240). That timer starts in `/init`: an earlier hang needs the power button.

## Verified on the phone
| Item | Result |
| --- | --- |
| Boot, CPUs, RAM | 8 CPUs (no pointer authentication), `MemTotal` 3660468 kB |
| USB network | CDC-ECM, 192.168.7.2, ping 0.2-0.6 ms, telnet shell |
| Timed reboot to bootloader | works (`host/rebootto.c`) |
| Host config | KPROBES, KALLSYMS_ALL, MODULES, CMA, 48-bit VA, 4 KB pages; KPTI "disabled by kernel configuration"; no SW PAN, no KASLR |
| Symbols fki needs | `kallsyms_lookup_name`, `set_memory_x`, `__do_kernel_fault`, `die`, `cma_alloc`, `alloc_contig_pages_noprof` present |
| Display | Samsung SOFEF00 panel, DPU 4.0.1, `fb0` console, connector `connected` 1080x2160 |
| GPU | msm DRM, `/dev/dri/renderD128`; SQE and GMU firmware load; OPPs 180/267/355/430 MHz. `vktest` passes (below) |

## GPU test: `vktest` on Linux (2026-11-26)
`host/gpu-userland.py` (Debian trixie Mesa 25.0.7 Turnip unpacked as files, `vktest.c` unchanged) then `host/mkboot.sh`; on the phone `/gpu/run`. Logs `logs/vktest-linux-*.txt`.
All steps pass. GPU pinned at 430 MHz, CPUs `performance`; the default governor gave the same bandwidth.

| | Linux, 430 MHz | iOS direct port, before the DDR vote (docs/GPU.md) |
| --- | --- | --- |
| fill, 32 MB | 1.72 GB/s | 1.18 GB/s |
| copy, 32 MB | 1.15 read + 1.15 write GB/s | 2.25 read + 2.25 write GB/s |
| empty submit round trip | mean 0.09-0.10 ms, best 0.07 ms | not in the docs |

- Not a fair like-for-like yet: other Mesa version, other GPU clock, and no iOS figure with the DDR vote (patch 0204) is recorded.
- During the test the GPU voted 7216000 kBps peak on `ebi`. The cause of the low copy rate is unknown. This microbenchmark does not show that the Linux driver stack is faster.

## Open
- Panel driver is not loaded by coldplug (`/init` now loads it; that change is not yet booted). One `DSI PLL(0) lock failed` warning at the first probe.
- `httpd` resets connections through the bridge; use `host/psh.py`.
- Wi-Fi, modem, ADSP, Bluetooth, IPA: no firmware in the image (it is in the vendor partition); remoteprocs wait for QMI.
- **Carve-out:** largest contiguous RAM is about 2.0 GB (0xfc402000-0x179270000), because `rmtfs-mem` (0xfc200000-0xfc401fff, modem shared memory) splits it from the 1.38 GB region at 0xa1c11000.
  Inferred, not tested: moving `rmtfs-mem` in the device tree could join them (about 3.4 GB).
- GPU maximum here is 430 MHz; the direct port ran 600 MHz. Matters for any speed comparison.
- Next: explain the copy rate, carve-out test, then gate 2 (`fki.ko`/`xnu.ko`).
