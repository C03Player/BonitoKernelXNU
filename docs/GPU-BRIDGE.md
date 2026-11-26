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

## Open: DeviceLost and a black screen (2026-11-26)

Verified on the phone:

- With the bridge on, only the boot logo shows; the Metal plugin then reports `DeviceLost`. The cause is a real GPU fault or hang: msm
  recovers, the service's fault count goes up, Turnip declares its device lost.
- Faults seen: `iova=0x20004000` and `iova=0x6002c010`, both CP writes. Each is a mapped address of a client window with the upper 32 bits
  gone (window bases `0x120000000`, `0x160000000`). Some hangs have no fault line.
- The packets in the CP's prefetch queue (devcoredump, `CP_ROQ_DBG`) carry the full 64-bit addresses; `CP_ADDR_MODE_CNTL` reads 1.
- `host/gpu/vatest.c` (Linux only, no iOS) writes through `CP_MEM_WRITE` and `CP_EVENT_WRITE` at `0x100000000`, `0x120000000` and
  `0x160000000` without a fault.
- Turnip's own messages: boot-arg `sweetmesalog=1` (`XNU_MESALOG=1 xnu-run`). `ADRENOD_DUMP=1` marks buffers for the crash dump, but msm
  does not dump imported buffers, so command buffer contents are not in it.

Inferred, not tested: the GPU reads partly stale command memory. The direct port requires pool memory without any cacheable alias. Here
Linux's linear map is a cacheable alias of the pool, and `fki.ko` maps the dma-buf with `DMA_ATTR_SKIP_CPU_SYNC`. Next experiments: clean
and invalidate the pool once before first use, and dump the faulting command buffers (an `mmap` for the dma-buf in `fki.ko`).
