/*
 * hfsreplay DEVICE [-n]: replay the journal of an HFS+ volume and mark it empty, as mounting it on iOS would, so that Linux may then write
 * to it. -n: only check and report. For the hosted system's tests, on the snapshot in RAM (docs/STORAGE.md), with nothing mounted.
 *
 * Journal (xnu bsd/vfs/vfs_journal.h): a header at the journal's start {magic "JNLx", endian, start, end, size, blhdr_size, checksum,
 * jhdr_size, sequence}, then a ring of transactions between start and end. Each is one or more block lists: a header of blhdr_size bytes
 * {max u16, num u16, bytes_used u32, checksum u32, pad u32, info[num] = {bnum u64, bsize u32, checksum u32 (info[0]: the transaction's number)}} followed by the blocks' data;
 * info[0] describes no block, bnum counts in jhdr_size units, bnum -1 marks a dropped block. Fields are little-endian here.
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAGIC 0x4a4e4c78u
#define ENDIAN 0x12345678u

struct header { uint32_t magic, endian; uint64_t start, end, size; uint32_t blhdr_size, checksum, jhdr_size, sequence; };
#define HEADER_SUMMED 44	/* the checksum covers the header up to sequence */
#define CHECK_CHECKSUMS 1	/* block list flags */
#define FIRST_HEADER 2		/* the first list of a transaction */
struct info { uint64_t bnum; uint32_t bsize, next; };
struct blhdr { uint16_t max_blocks, num_blocks; uint32_t bytes_used, checksum, flags; struct info info[]; };

static int fd;
static uint64_t base;	/* the journal's first byte on the device */
static struct header h;

static void die(const char *why) { fprintf(stderr, "hfsreplay: %s\n", why); exit(1); }

static uint32_t checksum(const void *p, size_t n)
{
	const unsigned char *c = p;
	uint32_t s = 0;
	for (size_t i = 0; i < n; i++)
		s = (s << 8) ^ (s + c[i]);
	return ~s;
}

static void rd(void *p, size_t n, uint64_t off) { if (pread(fd, p, n, off) != (ssize_t)n) die("read failed"); }
static void wr(const void *p, size_t n, uint64_t off) { if (pwrite(fd, p, n, off) != (ssize_t)n) die("write failed"); }

/* n bytes of the ring starting at journal offset *at (which advances, wrapping behind the header) */
static void ring(void *p, size_t n, uint64_t *at)
{
	unsigned char *out = p;
	while (n) {
		if (*at >= h.size)
			*at = h.jhdr_size + (*at - h.size);
		size_t part = h.size - *at < n ? h.size - *at : n;
		rd(out, part, base + *at);
		out += part;
		n -= part;
		*at += part;
	}
	if (*at >= h.size)
		*at = h.jhdr_size;
}

static uint32_t be32(const unsigned char *p) { return (uint32_t)p[0] << 24 | p[1] << 16 | p[2] << 8 | p[3]; }

int main(int argc, char **argv)
{
	int dry = argc > 2 && !strcmp(argv[2], "-n");
	unsigned char vh[512], ji[52];

	if (argc < 2 || (fd = open(argv[1], dry ? O_RDONLY : O_RDWR)) < 0)
		die("hfsreplay DEVICE [-n]");
	rd(vh, sizeof(vh), 1024);
	if (memcmp(vh, "H+", 2) && memcmp(vh, "HX", 2))
		die("not an HFS+ volume");
	if (!(be32(vh + 4) & 0x2000)) {
		printf("hfsreplay: the volume has no journal\n");
		return 0;
	}
	uint64_t block = be32(vh + 40), at_block = be32(vh + 12);
	rd(ji, sizeof(ji), at_block * block);
	if (be32(ji) & 4) {	/* kJIJournalNeedInitMask */
		printf("hfsreplay: the journal was never written\n");
		return 0;
	}
	base = (uint64_t)be32(ji + 36) << 32 | be32(ji + 40);
	rd(&h, sizeof(h), base);
	if (h.magic != MAGIC || h.endian != ENDIAN)
		die("no journal header");
	struct header check = h;
	check.checksum = 0;
	if (checksum(&check, HEADER_SUMMED) != h.checksum)
		die("the journal header's checksum is wrong");
	if (h.jhdr_size < 512 || h.blhdr_size < 512 || h.blhdr_size > 1 << 24 || h.start >= h.size || h.end >= h.size)
		die("the journal header makes no sense");

	struct blhdr *b = malloc(h.blhdr_size);
	unsigned char *data = malloc(1 << 20);
	if (!b || !data)
		die("no memory");
	if (h.end == 0)
		h.end = h.jhdr_size;
	/*
	 * First pass: find where the journal really ends. The header may be written after newer transactions, so those that follow its end
	 * with consecutive sequence numbers and good block checksums count too (as xnu's replay does). Nothing is written unless everything up
	 * to the header's end reads well.
	 */
	uint64_t at = h.start, last = h.end, walked = 0, txn = h.start;
	uint32_t sequence = 0, final_sequence = h.sequence;
	int beyond = 0;
	while (h.start != h.end) {
		uint64_t here = at;
		if (here == h.end)
			beyond = 1;
		if (beyond && !sequence)
			break;
		last = here;
		ring(b, h.blhdr_size, &at);
		uint32_t stored = b->checksum;
		b->checksum = 0;
		uint32_t seq = b->info[0].next;
		const char *bad = NULL;
		if (checksum(b, 32) != stored)
			bad = "a block list's checksum is wrong";
		else if (sequence && seq && seq != sequence && seq != sequence + 1)
			bad = "transaction numbers out of order";
		else if (!b->num_blocks || b->num_blocks > b->max_blocks || 16 + 16ul * b->num_blocks > h.blhdr_size)
			bad = "a block list makes no sense";
		if (bad) {
			if (beyond)
				break;	/* the journal ends here */
			die(bad);
		}
		if (b->flags & FIRST_HEADER)
			txn = here;
		walked += h.blhdr_size;
		for (unsigned i = 1; i < b->num_blocks && !bad; i++) {
			size_t n = b->info[i].bsize;
			if (n > 1 << 20 || (walked += n) > h.size) {
				bad = "a block is too large";
				break;
			}
			ring(data, n, &at);
			if (beyond && b->info[i].bnum != ~0ull && (b->flags & CHECK_CHECKSUMS) && b->info[i].next && checksum(data, n) != b->info[i].next)
				bad = "a block's checksum is wrong";
		}
		if (bad) {
			if (!beyond)
				die(bad);
			last = txn;
			break;
		}
		sequence = seq;
		if (seq)
			final_sequence = seq;
		last = at;
	}
	/* second pass: write the blocks of every list from start to there, in order */
	uint64_t lists = 0, blocks = 0;
	at = h.start;
	while (h.start != h.end && at != last) {
		ring(b, h.blhdr_size, &at);
		for (unsigned i = 1; i < b->num_blocks; i++) {
			size_t n = b->info[i].bsize;
			ring(data, n, &at);
			if (b->info[i].bnum == ~0ull)
				continue;
			if (!dry)
				wr(data, n, b->info[i].bnum * h.jhdr_size);
			blocks++;
		}
		lists++;
	}
	printf("hfsreplay: %llu block lists, %llu blocks%s\n", (unsigned long long)lists, (unsigned long long)blocks, dry ? " (not written)" : " written");
	if (!dry) {
		if (fsync(fd))
			die("sync failed");
		h.start = h.end = h.start == h.end ? h.end : last;
		h.sequence = final_sequence;
		h.checksum = 0;
		h.checksum = checksum(&h, HEADER_SUMMED);
		wr(&h, sizeof(h), base);
		if (fsync(fd))
			die("sync failed");
		printf("hfsreplay: journal empty\n");
	}
	return 0;
}
