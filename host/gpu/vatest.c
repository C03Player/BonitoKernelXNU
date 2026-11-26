/* vatest: does the CP write to the full 64-bit address? Writes through CP_MEM_WRITE and CP_EVENT_WRITE at a chosen GPU address. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <drm/drm.h>
#include <drm/msm_drm.h>
static int fd;
static uint32_t pkt7(uint32_t op, uint32_t n) { return 0x70000000u | n | (!__builtin_parity(n) << 15) | (op << 16) | (!__builtin_parity(op) << 23); }
static void *bo(uint64_t iova, uint32_t *h)
{
	struct drm_msm_gem_new n = { .size = 16384, .flags = MSM_BO_WC };
	if (ioctl(fd, DRM_IOCTL_MSM_GEM_NEW, &n)) { perror("new"); exit(1); }
	struct drm_msm_gem_info i = { .handle = n.handle, .info = MSM_INFO_SET_IOVA, .value = iova };
	if (ioctl(fd, DRM_IOCTL_MSM_GEM_INFO, &i)) { perror("set iova"); exit(1); }
	i.info = MSM_INFO_GET_OFFSET; i.value = 0;
	if (ioctl(fd, DRM_IOCTL_MSM_GEM_INFO, &i)) { perror("offset"); exit(1); }
	*h = n.handle;
	return mmap(NULL, 16384, PROT_READ | PROT_WRITE, MAP_SHARED, fd, i.value);
}
int main(int argc, char **argv)
{
	fd = open("/dev/dri/renderD128", O_RDWR);
	uint64_t base = strtoull(argc > 1 ? argv[1] : "0x160000000", 0, 0);
	struct drm_msm_submitqueue q = { .prio = 1 };
	if (ioctl(fd, DRM_IOCTL_MSM_SUBMITQUEUE_NEW, &q)) { perror("queue"); return 1; }
	uint32_t hd, hc;
	volatile uint32_t *d = bo(base, &hd);
	uint32_t *c = bo(base + 0x4000, &hc), n = 0;
	memset((void *)d, 0, 16384);
	for (int k = 0; k < 4; k++) {
		uint64_t a = base + k * 8;
		c[n++] = pkt7(0x3d, 4); c[n++] = a; c[n++] = a >> 32; c[n++] = 0x100 + k; c[n++] = 0;
	}
	uint64_t a = base + 0x100;	/* CP_EVENT_WRITE CACHE_FLUSH_TS */
	c[n++] = pkt7(0x46, 4); c[n++] = 4; c[n++] = a; c[n++] = a >> 32; c[n++] = 0x200;
	c[n++] = pkt7(0x26, 0);	/* CP_WAIT_FOR_IDLE */
	struct drm_msm_gem_submit_bo b[2] = { { .flags = 3, .handle = hc }, { .flags = 3, .handle = hd } };
	struct drm_msm_gem_submit_cmd cmd = { .type = MSM_SUBMIT_CMD_BUF, .submit_idx = 0, .size = n * 4 };
	struct drm_msm_gem_submit s = { .flags = MSM_PIPE_3D0, .nr_bos = 2, .bos = (uintptr_t)b, .nr_cmds = 1, .cmds = (uintptr_t)&cmd, .queueid = q.id };
	if (ioctl(fd, DRM_IOCTL_MSM_GEM_SUBMIT, &s)) { perror("submit"); return 1; }
	struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); t.tv_sec += 2;
	struct drm_msm_wait_fence w = { .fence = s.fence, .queueid = q.id, .timeout = { t.tv_sec, t.tv_nsec } };
	int r = ioctl(fd, DRM_IOCTL_MSM_WAIT_FENCE, &w);
	printf("base %#llx wait %d: mem %x %x %x %x event %x\n", (unsigned long long)base, r ? -errno : 0, d[0], d[2], d[4], d[6], d[0x40]);
	return 0;
}
