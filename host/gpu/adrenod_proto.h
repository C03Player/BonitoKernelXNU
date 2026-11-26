/* SPDX-License-Identifier: MIT */
/*
 * The GPU bridge's messages (docs/GPU-BRIDGE.md): the hosted XNU (bsd/dev/sweet_gpu_host.c, through linux64_hostcall) asks adrenod, the Linux
 * service that owns the Adreno's render node. One request, one reply; the reply's status is 0 or -errno.
 */
#ifndef ADRENOD_PROTO_H
#define ADRENOD_PROTO_H
#include <stdint.h>

#define AGPU_MAGIC 0x55504741u	/* 'AGPU' */
#define AGPU_VERSION 1
#define AGPU_MAX_PAGES 16384	/* per MAP request (64 MiB of 4 KiB pages) */
#define AGPU_MAX_IBS 16
#define AGPU_WAIT_SLICE_NS 20000000ull	/* the longest a WAIT holds the calling XNU CPU */

enum agpu_op {
	AGPU_INFO = 1,		/* -> v[0] chip id, v[1] GMEM bytes, v[2] GMEM base, v[3] VA start, v[4] VA size, v[5] highest bank bit,
				 *    v[6] UBWC swizzle, v[7] macrotile mode | uche trap base in payload (u64) */
	AGPU_MAP = 2,		/* a0 iova, n pages; payload: n u64 physical addresses (4 KiB each) */
	AGPU_UNMAP = 3,		/* a0 iova, a1 bytes: every mapping inside the range */
	AGPU_SUBMIT = 4,	/* n IBs; payload: n struct agpu_ib -> v[0] fence */
	AGPU_WAIT = 5,		/* a0 fence, a1 timeout ns (at most AGPU_WAIT_SLICE_NS) -> status -ETIMEDOUT while pending */
	AGPU_TIMESTAMP = 6,	/* -> v[0] GPU always-on counter */
	AGPU_FAULTS = 7,	/* -> v[0] faults of the service's queue */
};

struct agpu_ib { uint64_t iova; uint32_t dwords; uint32_t pad; };

struct agpu_req {
	uint32_t magic, op, n, pad;
	uint64_t a0, a1, a2;
	/* payload follows */
};

struct agpu_rep {
	uint32_t magic;
	int32_t status;
	uint32_t n, pad;
	uint64_t v[8];
	/* payload follows */
};
#endif
