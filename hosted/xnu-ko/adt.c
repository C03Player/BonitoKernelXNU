// SPDX-License-Identifier: APSL-2.0
// ADT: node = {u32 nProperties, u32 nChildren}, then properties
// {char name[32]; u32 length; value padded to 4}, then children.
#include "xrt.h"
#include "adt.h"

void adt_init(struct adt *a, void *buf, unsigned long cap)
{
	a->buf = a->p = buf; a->end = a->buf + cap; a->err = 0;
	a->hdr = 0; a->extra = 0; a->extra_len = 0; a->node = 0;
}

static void put(struct adt *a, const void *v, unsigned long n)
{
	if (a->p + n > a->end) { a->err = 1; return; }
	x_memcpy(a->p, v, n); a->p += n;
}

void adt_node(struct adt *a, unsigned nprops, unsigned nchildren)
{
	unsigned h[2] = { 0, nchildren };	/* the count follows the properties actually written */
	(void)nprops;
	a->hdr = (unsigned *)a->p;
	a->node = 0;
	put(a, h, sizeof(h));
}

static int same(const char *a, const char *b)	/* b is at most 32 bytes */
{
	for (int i = 0; i < 32; i++) {
		if (a[i] != b[i]) return 0;
		if (!a[i]) return 1;
	}
	return 1;
}

static void emit(struct adt *a, const char *name, const void *val, unsigned len);

/* the next record after `off`, or 0 at the end / on a malformed one */
static unsigned long next_extra(struct adt *a, unsigned long off, unsigned *len)
{
	if (off + 68 > a->extra_len) return 0;
	x_memcpy(len, a->extra + off + 64, 4);
	if (*len > a->extra_len - off - 68) return 0;
	return off + 68 + ((*len + 3UL) & ~3UL);
}

void adt_extras(struct adt *a, const char *node)
{
	unsigned len;
	unsigned long off = 0, n;

	a->node = node;
	for (; (n = next_extra(a, off, &len)) != 0; off = n)
		if (same(node, (const char *)a->extra + off))
			emit(a, (const char *)a->extra + off + 32, a->extra + off + 68, len);
}

void adt_prop(struct adt *a, const char *name, const void *val, unsigned len)
{
	unsigned l;
	unsigned long off = 0, n;

	if (a->node)
		for (; (n = next_extra(a, off, &l)) != 0; off = n)
			if (same(a->node, (const char *)a->extra + off) && same(name, (const char *)a->extra + off + 32))
				return;		/* given from outside */
	emit(a, name, val, len);
}

static void emit(struct adt *a, const char *name, const void *val, unsigned len)
{
	char n[32] = { 0 };
	unsigned long l = x_strlen(name);
	static const unsigned char zero[4];
	x_memcpy(n, name, l < 31 ? l : 31);
	put(a, n, 32);
	put(a, &len, 4);
	put(a, val, len);
	put(a, zero, (4 - (len & 3)) & 3);
	if (!a->err && a->hdr) a->hdr[0]++;
}

void adt_prop_str(struct adt *a, const char *name, const char *s) { adt_prop(a, name, s, x_strlen(s) + 1); }
void adt_prop_u32(struct adt *a, const char *name, unsigned v) { adt_prop(a, name, &v, 4); }
void adt_prop_u64(struct adt *a, const char *name, unsigned long long v) { adt_prop(a, name, &v, 8); }
