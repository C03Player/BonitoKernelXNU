// SPDX-License-Identifier: APSL-2.0
/* Apple device tree (ADT) writer, written from the documented flattened format. */
#pragma once
struct adt {
	unsigned char *buf, *p, *end; int err;
	unsigned *hdr;				/* the current node's property count, kept as properties are written */
	const unsigned char *extra; unsigned long extra_len; const char *node;	/* properties given from outside (adt_extras) */
};
void adt_init(struct adt *a, void *buf, unsigned long cap);
void adt_node(struct adt *a, unsigned nprops, unsigned nchildren);
void adt_prop(struct adt *a, const char *name, const void *val, unsigned len);
void adt_prop_str(struct adt *a, const char *name, const char *s);
void adt_prop_u32(struct adt *a, const char *name, unsigned v);
void adt_prop_u64(struct adt *a, const char *name, unsigned long long v);
/* Right after adt_node: write the outside properties of the node called `node`; later adt_prop calls of the same names are dropped. Records:
 * char node[32]; char name[32]; u32 length; value padded to 4. */
void adt_extras(struct adt *a, const char *node);
static inline unsigned long adt_size(struct adt *a) { return a->p - a->buf; }
