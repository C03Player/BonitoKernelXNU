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
