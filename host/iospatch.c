/*
 * iospatch DEVICE LIST: change instructions of iOS code on the root disk before the hosted system reads it. DEVICE is the snapshot XNU gets
 * (/dev/mapper/iosroot), so the changes live in RAM and the partition itself stays untouched.
 * LIST (host/iospatches.py): one patch per line, "HINT SIG AT NEW": bytes of the original system that appear once (hex), the byte offset of
 * the replaced part inside them, its replacement (hex bytes) and where on the device SIG probably is. Instructions and the code signature's
 * page hashes are both patched this way.
 * A patch is looked for at HINT first and then on the whole device; one already applied is recognized.
 */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <linux/fs.h>
#include <unistd.h>

#define CHUNK (4 << 20)

static int hex(const char *s, unsigned char *out, int max)
{
	int n = strlen(s) / 2;
	unsigned v;

	if (n > max)
		return 0;
	for (int i = 0; i < n; i++) {
		if (sscanf(s + 2 * i, "%2x", &v) != 1)
			return 0;
		out[i] = v;
	}
	return n;
}

/* 1: the original bytes are at off, 2: the patched ones, 0: neither */
static int at_offset(int fd, long long off, const unsigned char *sig, const unsigned char *done, int n)
{
	unsigned char b[64];

	if (off < 0 || pread(fd, b, n, off) != n)
		return 0;
	return !memcmp(b, sig, n) ? 1 : !memcmp(b, done, n) ? 2 : 0;
}

int main(int argc, char **argv)
{
	unsigned char sig[64], done[64];
	unsigned char rep[64];
	char line[512], text[160], with[160];
	long long hint;
	int fd, at, n, m, failed = 0;
	FILE *list;

	if (argc != 3 || (fd = open(argv[1], O_RDWR)) < 0 || !(list = fopen(argv[2], "r"))) {
		fprintf(stderr, "iospatch DEVICE LIST\n");
		return 2;
	}
	unsigned char *buf = malloc(CHUNK + 64);
	while (buf && fgets(line, sizeof(line), list)) {
		if (sscanf(line, "%lli %128s %d %128s", &hint, text, &at, with) != 4 || !(n = hex(text, sig, sizeof(sig))) ||
		    !(m = hex(with, rep, sizeof(rep))) || at < 0 || at + m > n) {
			failed = printf("iospatch: bad line: %s", line);
			continue;
		}
		memcpy(done, sig, n);
		memcpy(done + at, rep, m);
		long long off = hint;
		int found = at_offset(fd, off, sig, done, n);
		for (long long pos = 0; !found; pos += CHUNK) {
			ssize_t got = pread(fd, buf, CHUNK + n, pos);
			if (got < n)
				break;
			unsigned char *a = memmem(buf, got, sig, n), *b = memmem(buf, got, done, n);
			if (a || b) {
				off = pos + ((a ? a : b) - buf);
				found = a ? 1 : 2;
			}
		}
		if (found == 1 && pwrite(fd, rep, m, off + at) != m)
			found = 0;
		if (found)
			printf("iospatch: %d bytes at device offset %#llx %s\n", m, off + at, found == 1 ? "patched" : "were already patched");
		else
			failed = printf("iospatch: not found: %s\n", text);
	}
	if (fsync(fd))
		failed = 1;
	ioctl(fd, BLKFLSBUF, 0);
	return failed ? 1 : 0;
}
