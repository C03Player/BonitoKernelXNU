# GPU bridge: iOS Metal on Linux's Adreno driver (design, 2026-11-26)

iOS draws with Metal through the direct port's stack, unchanged: SweetMetal2 (Metal on Vulkan) -> Turnip built for Darwin (`tu_knl_darwin`) ->
the kernel user client `SweetAccelerator` (NativeAdreno ABI v1, `bonito/userland/phone/turnip/NativeAdrenoABI.h`).
On the direct port that user client drives the Adreno itself (`bsd/dev/bonito_gpu.c`). Hosted, the GPU is Linux's (msm DRM, `/dev/dri/renderD128`),
so the user client's backend, about twelve C functions, is reimplemented as calls to a Linux service.

```
iOS process (Turnip)                 XNU (hosted)                               Linux
NativeAdreno ABI  -> SweetAccelerator -> sweet_gpu_host_*  -- linux64_hostcall -->  fki.ko /dev/xnu-hostcall -> adrenod (render node, msm ioctls)
buffer memory:  XNU physical pages (GPU pool or the client's pinned pages) -- XNU_HOSTCALL_DMABUF --> dma-buf -> PRIME import -> MSM_INFO_SET_IOVA
```

| User client backend (direct port) | Hosted |
| --- | --- |
| `sweet_gpu_window_alloc` (GPU address window) | `MSM_PARAM_VA_START` / `MSM_PARAM_VA_SIZE` of the service's DRM file |
| `sweet_gpu_pool_alloc/free/avail` (memory outside XNU's VM) | a pool `xnu.ko` reserves after XNU's RAM (`gpu_pool_mb`), described in `/chosen` |
| `sweet_gpu_map_at(iova, pages)` | the pages become a dma-buf (fki.ko), imported (PRIME) and placed at `iova` (`MSM_INFO_SET_IOVA`) |
| `sweet_gpu_unmap_at` | `GEM_CLOSE` of the imported buffers in that range |
| `sweet_gpu_submit_v2(iova[], dwords[])` | `MSM_GEM_SUBMIT` on one submit queue: each IB as a command in the buffer that contains it |
| `sweet_gpu_wait_fence_ns`, `sweet_gpu_timestamp`, `sweet_gpu_lost` | `MSM_WAIT_FENCE`, `MSM_PARAM_TIMESTAMP`, `MSM_PARAM_FAULTS` |

Memory stays where it is: no copies. Pool pages are mapped write-combined in XNU (as on the direct port); imported IOSurface pages are cached in XNU and
flushed by the user client before use (as on the direct port). Device information (chip id, GMEM, UBWC) comes from msm's parameters.

## Tests
- hosted28 (2026-11-26): the bridge works end to end: `adrenod` up (chip 0x6010500, GPU addresses 0x100000000 + 4 GiB), the Metal plugin opened the
  user client, buffers were mapped and the first command buffers ran on the Adreno. Then GPU translation faults and a hang recovery: every client got
  the whole address range, so a second client's buffers collided with the first's (`MAP ... -> -28`). Fixed: eight windows, one per client.

## Solved: DeviceLost and a black screen (2026-11-26)

Symptoms: GPU faults with the upper address bits gone (`iova=0x2002c010`, `0x6002c010`), `CP | opcode error`, hangs, `DeviceLost`.

Cause: hosted XNU is entered at `arm_init` and runs on Linux's `MAIR_EL1`. XNU's write-combined index (1) is Linux's "normal tagged" slot,
which is write-back cacheable, so the GPU read stale memory. Fix: under `SWEET_HOSTED` the indices in `osfmk/arm64/proc_reg.h` name Linux's
slots (write-combined 2, write-back 0, devices 3 and 4). `xnu.ko` also cleans the GPU pool from the CPU caches once, because Linux zeroes it
through its cacheable mapping.

Verified with build 45907541142 (log `hosted43`): all GPU clients open their device, no GPU fault, opcode error or hang, no `DeviceLost`,
GPU-rendered lock and home screen, 13 to 42 swaps per second in the 5 s windows around unlocking.

Rectangles of older frames (2026-11-27, `host/uitour.py` screenshots) had the direct port's two causes again: msm flushes the caches only at
a submit's end, so `adrenod` now puts a colour/depth cache flush and a wait between command buffers; and the display's fence checks still
asked the direct port's GPU driver, so they now use the host GPU's fences (`sweet_gpu_host_latest_fence`, `_fence_done`). After both, one
screenshot tour showed no such rectangles; one faint line on a just-woken lock screen is unexplained.

**Solved 2026-11-27 (stale text).** The cause below is fixed at its source: our Metal plugin's runtime handed out an existing GPU import
again when memory was asked for at the same address and length. That one call is patched out at boot (`host/iospatches.py`,
docs/IOS-PATCHES.md), so every such buffer is imported anew. `host/uistale.py` on one boot of the phone: 6 of 14 rounds wrong before the
patch, 0 and 0 of 14 after it (patched in RAM). About 1150 mappings stay live instead of 740. The history follows.

Open: after scrolling a list, some rows show wrong content (also seen by the user: the Accessibility label showing the clock): another row's text ("Safari" beside the Sounds icon) or garbled glyphs.
`host/uistale.py` reproduces it (Settings at the top: scroll down, back, compare; blocks that differ beyond a 1 pixel settle offset; earlier
"14 of 14" counts included that offset).

**Cause (checked by the kernel, 2026-11-27):** a buffer the Metal runtime imported from backboardd's memory keeps the pages it had at the
import, while the same address later maps other pages. Boot-arg `sweetgpuremap=0` logs it (`import 0x... no longer at its pages`), about
once per submit at first. The runtime looks live imports up by address, so new content reaches new pages and the GPU samples the old ones.

| try | rounds with wrong content | note |
|---|---|---|
| fence waits fixed (below) | 5 of 14 | |
| `sweettudebug=noubwc` | 7 of 14 | |
| `sweettudebug=flushall,syncdraw` | 3 of 14 | |
| `sweettudebug=sysmem` | 8 of 14 | |
| `sweetgpuremap=0` (check only) | 4 of 14 | mismatches logged |
| `sweetgpuremap=1` (import again) | not measurable | 4 of 4 runs: backboardd stops swapping within seconds, no GPU fault, other GPU clients go on |
| `sweetgpuremap=3` (read-only pin) | not measurable | 1 run: some re-imports refused (swaps went on); screen frozen soon after the first that succeeded, so a write pin copying pages is not the cause of the freeze |
| `sweetgpuclean=1`, `sweetfullarea=1` | wrong content seen | kernel cleans imports before each submit; no partial render areas |
| `sweetnoworker=1` | invalid | GPU fault, then `DeviceLost`: the screen froze |

Next: find why the compositor stops after a re-import (its threads' state is not visible from Linux), or make the runtime drop an import when
its memory is released (needs a rebuilt iOS-side plugin, `bonito/userland/phone/metal2`). Open too: why the pages differ at all (a write pin
of a copy-on-write range could make its own pages).

Fixed on the way: the XNU side compared the service's `-ETIMEDOUT` (Linux, 110) with XNU's (60), so every fence wait gave up after 20 ms.

Open: the Photos widget is black.

Debug switches: `XNU_MESALOG=1 xnu-run` (Turnip's messages on the console), `ADRENOD_V=-vv`, `ADRENOD_DUMP=1`; `host/gpu/vatest.c` writes to
high GPU addresses from Linux alone.

## GPU clock above 430 MHz (tried 2026-11-27, does not work)

This phone's speed grade (bin 0) is rated for 430 MHz in the stock and mainline clock tables. Enabling the 504 MHz entry for it (bit 0
of `opp-supported-hw` in the device tree) left the GPU unable to start: `gpu hw init failed`, `GMU firmware fault`, no frames (one boot;
the next boot at 430 MHz was fine). The option was removed again. Baseline at 430 MHz, scrolling Settings with injected swipes: 11.6
frames per second over 7 five-second windows, hottest sensor 52.5 C.

Blur (2026-11-27): the same Settings scroll gave 12.3 frames per second as is and 12.9 with Reduce Transparency on (one run each, same
boot; earlier runs without it: 11.6 and 12.2). A faster blur would gain little there. Not measured: home screen, Control Center, folders.
