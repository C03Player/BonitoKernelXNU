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

Open: after scrolling a list, some rows keep another row's text (Settings: "Emergency SO" beside the Airplane Mode icon). Reproduced in
14 of 14 rounds by `host/uistale.py` (Settings at the top: scroll down, back, compare). The Metal plugin cleans the CPU caches for the
surfaces and no-copy buffers of each command buffer, and an extra GPU cache invalidate in `adrenod` changed nothing (14 of 14), so neither
cache explains it by itself. Further tries (boot-args write the plugin's switch files):

| try | result |
|---|---|
| `sweetgpuclean=1`: kernel cleans every imported buffer before each submit | 12 of 12 rounds differ; wrong pieces are parts of other labels (`Not Connectec`, `lar Calendar`) |
| `sweetfullarea=1`: no partial render areas | 10 of 10 rounds differ |
| `sweetnoworker=1`: translation on the caller's thread | invalid: a GPU fault early in the run (CP read, address with its upper bits gone), then `DeviceLost`; the screen froze |

Next: how the plugin tracks surfaces whose content changed (needs a rebuilt iOS-side plugin). Do not use `sweetnoworker=1`.

Open: the Photos widget is black.

Debug switches: `XNU_MESALOG=1 xnu-run` (Turnip's messages on the console), `ADRENOD_V=-vv`, `ADRENOD_DUMP=1`; `host/gpu/vatest.c` writes to
high GPU addresses from Linux alone.
