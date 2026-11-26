/* SPDX-License-Identifier: MIT */
/*
 * adrenod: the Linux side of the GPU bridge (docs/GPU-BRIDGE.md). Serves the hosted XNU's GPU requests (adrenod_proto.h) from /dev/xnu-hostcall
 * with the msm DRM driver: XNU's physical pages become dma-bufs (fki.ko XNU_HOSTCALL_DMABUF), imported (PRIME) and placed at the GPU
 * addresses XNU chose (MSM_INFO_SET_IOVA); command buffers go out with MSM_GEM_SUBMIT on one submit queue.
 *   adrenod [-v] [/dev/dri/renderD128]
 */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>
#include <drm/drm.h>
#include <drm/msm_drm.h>
#include "adrenod_proto.h"

struct xnu_hostcall_dmabuf { uint64_t pa, n; int32_t fd; uint32_t pad; };
#define XNU_HOSTCALL_DMABUF _IOWR('X', 4, struct xnu_hostcall_dmabuf)

#define MAX_MAPS 65536
static struct map { uint64_t iova, len; uint32_t handle; } maps[MAX_MAPS];
static unsigned nmaps;
static int drm, hc, verbose;
static uint32_t queue;
static uint64_t submits, maps_made;
static uint32_t last_fence;
static int do_wait(uint32_t fence, uint64_t ns);

static int param(uint32_t p, uint64_t *v)
{
	struct drm_msm_param a = { .pipe = MSM_PIPE_3D0, .param = p };
	if (ioctl(drm, DRM_IOCTL_MSM_GET_PARAM, &a))
		return -errno;
	*v = a.value;
	return 0;
}

static struct map *find(uint64_t iova)
{
	for (unsigned i = 0; i < nmaps; i++)
		if (iova >= maps[i].iova && iova < maps[i].iova + maps[i].len)
			return &maps[i];
	return NULL;
}

static int do_map(uint64_t iova, const uint64_t *pa, uint32_t n)
{
	struct xnu_hostcall_dmabuf d = { .pa = (uintptr_t)pa, .n = n };
	struct drm_prime_handle ph = { 0 };
	struct drm_msm_gem_info gi = { 0 };
	int err;

	if (nmaps == MAX_MAPS)
		return -ENOMEM;
	if (ioctl(hc, XNU_HOSTCALL_DMABUF, &d))
		return -errno;
	ph.fd = d.fd;
	err = ioctl(drm, DRM_IOCTL_PRIME_FD_TO_HANDLE, &ph) ? -errno : 0;
	close(d.fd);
	if (err)
		return err;
	gi.handle = ph.handle;
	gi.info = MSM_INFO_SET_IOVA;
	gi.value = iova;
	if (ioctl(drm, DRM_IOCTL_MSM_GEM_INFO, &gi)) {
		err = -errno;
		struct drm_gem_close c = { .handle = ph.handle };
		ioctl(drm, DRM_IOCTL_GEM_CLOSE, &c);
		return err;
	}
	maps[nmaps++] = (struct map){ iova, (uint64_t)n << 12, ph.handle };
	maps_made++;
	return 0;
}

static int do_unmap(uint64_t iova, uint64_t len)
{
	int found = 0;

	/* as the direct port's window and buffer release: the GPU finishes what it was given before memory goes (up to 1 s) */
	for (int i = 0; i < 50 && last_fence && do_wait(last_fence, AGPU_WAIT_SLICE_NS) == -ETIMEDOUT; i++)
		;
	for (unsigned i = 0; i < nmaps;) {
		if (maps[i].iova >= iova && maps[i].iova + maps[i].len <= iova + len) {
			struct drm_gem_close c = { .handle = maps[i].handle };
			ioctl(drm, DRM_IOCTL_GEM_CLOSE, &c);
			maps[i] = maps[--nmaps];
			found = 1;
		} else {
			i++;
		}
	}
	return found ? 0 : -ENOENT;
}

/*
 * msm maps a buffer into the GPU's page tables only while a submit lists it (MSM_INFO_SET_IOVA just reserves the address; test hosted29:
 * translation faults on render targets). So every live buffer goes into every submit, the command buffers first.
 */
static struct drm_msm_gem_submit_bo bos[MAX_MAPS];
static uint32_t dumpflag;	/* ADRENOD_DUMP=1: buffer contents go into the crash dump (/sys/class/devcoredump) */

static int do_submit(const struct agpu_ib *ib, uint32_t n, uint64_t *fence)
{
	struct drm_msm_gem_submit_cmd cmds[AGPU_MAX_IBS];
	uint32_t nbos = 0;

	if (n == 0 || n > AGPU_MAX_IBS)
		return -EINVAL;
	memset(cmds, 0, sizeof(cmds));
	for (uint32_t i = 0; i < n; i++) {
		struct map *m = find(ib[i].iova);
		uint32_t idx;
		if (!m || ib[i].iova + (uint64_t)ib[i].dwords * 4 > m->iova + m->len)
			return -EFAULT;
		for (idx = 0; idx < nbos && bos[idx].handle != m->handle; idx++)
			;
		if (idx == nbos)
			bos[nbos++] = (struct drm_msm_gem_submit_bo){ .flags = MSM_SUBMIT_BO_READ | MSM_SUBMIT_BO_WRITE | dumpflag, .handle = m->handle };
		cmds[i].type = MSM_SUBMIT_CMD_BUF;
		cmds[i].submit_idx = idx;
		cmds[i].submit_offset = (uint32_t)(ib[i].iova - m->iova);
		cmds[i].size = ib[i].dwords * 4;
	}
	uint32_t ncmd = nbos;
	for (unsigned i = 0; i < nmaps; i++) {
		uint32_t j;
		for (j = 0; j < ncmd && bos[j].handle != maps[i].handle; j++)
			;
		if (j == ncmd)
			bos[nbos++] = (struct drm_msm_gem_submit_bo){ .flags = MSM_SUBMIT_BO_READ | MSM_SUBMIT_BO_WRITE | dumpflag, .handle = maps[i].handle };
	}
	struct drm_msm_gem_submit s = {
		.flags = MSM_PIPE_3D0 | MSM_SUBMIT_NO_IMPLICIT, .nr_bos = nbos, .nr_cmds = n,
		.bos = (uintptr_t)bos, .cmds = (uintptr_t)cmds, .queueid = queue,
	};
	if (ioctl(drm, DRM_IOCTL_MSM_GEM_SUBMIT, &s))
		return -errno;
	*fence = s.fence;
	last_fence = s.fence;
	submits++;
	return 0;
}

static int do_wait(uint32_t fence, uint64_t ns)
{
	struct timespec now;
	if (ns > AGPU_WAIT_SLICE_NS)
		ns = AGPU_WAIT_SLICE_NS;
	clock_gettime(CLOCK_MONOTONIC, &now);
	uint64_t t = (uint64_t)now.tv_sec * 1000000000ull + now.tv_nsec + ns;
	struct drm_msm_wait_fence w = { .fence = fence, .queueid = queue,
		.timeout = { .tv_sec = (int64_t)(t / 1000000000ull), .tv_nsec = (int64_t)(t % 1000000000ull) } };
	if (ns == 0)
		w.flags = MSM_WAIT_FENCE_BOOST;
	return ioctl(drm, DRM_IOCTL_MSM_WAIT_FENCE, &w) ? -errno : 0;
}

static size_t serve(const uint8_t *in, size_t inlen, uint8_t *out)
{
	const struct agpu_req *q = (const void *)(in + 8);
	struct agpu_rep *r = (void *)(out + 8);
	const void *payload = q + 1;
	size_t plen = inlen - 8 - sizeof(*q);

	memcpy(out, in, 8);	/* the call's sequence number */
	memset(r, 0, sizeof(*r));
	r->magic = AGPU_MAGIC;
	if (inlen < 8 + sizeof(*q) || q->magic != AGPU_MAGIC) {
		r->status = -EPROTO;
		return 8 + sizeof(*r);
	}
	switch (q->op) {
	case AGPU_INFO: {
		static const uint32_t p[] = { MSM_PARAM_CHIP_ID, MSM_PARAM_GMEM_SIZE, MSM_PARAM_GMEM_BASE, MSM_PARAM_VA_START, MSM_PARAM_VA_SIZE,
					      MSM_PARAM_HIGHEST_BANK_BIT, MSM_PARAM_UBWC_SWIZZLE, MSM_PARAM_MACROTILE_MODE };
		for (unsigned i = 0; i < 8 && !r->status; i++)
			r->status = param(p[i], &r->v[i]);
		uint64_t trap = 0;
		if (!r->status && param(MSM_PARAM_UCHE_TRAP_BASE, &trap))
			trap = 0x1fffffffff000ull;
		memcpy(r + 1, &trap, 8);
		r->n = 1;
		return 8 + sizeof(*r) + 8;
	}
	case AGPU_MAP:
		r->status = q->n == 0 || q->n > AGPU_MAX_PAGES || plen < (size_t)q->n * 8 ? -EINVAL : do_map(q->a0, payload, q->n);
		break;
	case AGPU_UNMAP:
		r->status = do_unmap(q->a0, q->a1);
		break;
	case AGPU_SUBMIT:
		r->status = plen < (size_t)q->n * sizeof(struct agpu_ib) ? -EINVAL : do_submit(payload, q->n, &r->v[0]);
		break;
	case AGPU_WAIT:
		r->status = do_wait((uint32_t)q->a0, q->a1);
		break;
	case AGPU_TIMESTAMP:
		r->status = param(MSM_PARAM_TIMESTAMP, &r->v[0]);
		break;
	case AGPU_FAULTS: {
		struct drm_msm_submitqueue_query qq = { .data = (uintptr_t)&r->v[0], .id = queue, .param = MSM_SUBMITQUEUE_PARAM_FAULTS, .len = 4 };
		uint32_t f = 0;
		qq.data = (uintptr_t)&f;
		r->status = ioctl(drm, DRM_IOCTL_MSM_SUBMITQUEUE_QUERY, &qq) ? -errno : 0;
		r->v[0] = f;
		break;
	}
	default:
		r->status = -ENOSYS;
	}
	return 8 + sizeof(*r);
}

int main(int argc, char **argv)
{
	if (getenv("ADRENOD_DUMP"))
		dumpflag = MSM_SUBMIT_BO_DUMP;
	const char *node = "/dev/dri/renderD128";
	for (int a = 1; a < argc; a++) {
		if (argv[a][0] == '-' && argv[a][1] == 'v')
			for (const char *c = argv[a] + 1; *c == 'v'; c++)
				verbose++;
		else
			node = argv[a];
	}
	drm = open(node, O_RDWR | O_CLOEXEC);
	if (drm < 0) {
		perror(node);
		return 1;
	}
	struct drm_msm_submitqueue sq = { .flags = 0, .prio = 1 };
	if (ioctl(drm, DRM_IOCTL_MSM_SUBMITQUEUE_NEW, &sq)) {
		perror("SUBMITQUEUE_NEW");
		return 1;
	}
	queue = sq.id;
	uint64_t chip = 0, vs = 0, vz = 0;
	param(MSM_PARAM_CHIP_ID, &chip);
	param(MSM_PARAM_VA_START, &vs);
	param(MSM_PARAM_VA_SIZE, &vz);
	hc = open("/dev/xnu-hostcall", O_RDWR | O_CLOEXEC);
	if (hc < 0) {
		perror("/dev/xnu-hostcall");
		return 1;
	}
	static uint8_t msg[8 + sizeof(struct agpu_req) + AGPU_MAX_PAGES * 8], rep[8 + sizeof(struct agpu_rep) + 64];
	fprintf(stderr, "adrenod: %s chip %#llx, GPU addresses %#llx + %#llx, queue %u\n", node, (unsigned long long)chip,
		(unsigned long long)vs, (unsigned long long)vz, queue);
	time_t last = time(NULL);
	for (;;) {
		ssize_t n = read(hc, msg, sizeof(msg));
		if (n < 0) {
			if (errno == EINTR || errno == EAGAIN)
				continue;
			perror("read");
			return 1;
		}
		const struct agpu_req *q = (const void *)(msg + 8);
		size_t rn = serve(msg, (size_t)n, rep);
		const struct agpu_rep *r = (const void *)(rep + 8);
		if (verbose > 1 || (verbose && r->status && !(q->op == AGPU_WAIT && r->status == -ETIMEDOUT)))
			fprintf(stderr, "adrenod: op %u a0 %#llx n %u -> %d\n", q->op, (unsigned long long)q->a0, q->n, r->status);
		if (verbose && time(NULL) - last >= 5) {
			last = time(NULL);
			fprintf(stderr, "adrenod: %llu submits, %llu maps made, %u live\n", (unsigned long long)submits, (unsigned long long)maps_made, nmaps);
		}
		if (write(hc, rep, rn) < 0 && errno != ESTALE)
			perror("write");
	}
}
