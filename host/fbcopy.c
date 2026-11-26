/* fbcopy SRC: show the hosted system's framebuffer (SRC, a file of 1080x2160 rows of 4320 bytes that xnu.ko rewrites) on /dev/fb0, whose rows may be longer. about 30 Hz. */
#include <fcntl.h>
#include <linux/fb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

/*
 * Frame counter: the number of different frames that reached the screen in the last second, drawn in the top-left corner (FPS=0 in the
 * environment turns it off). A frame counts when its content differs from the one shown before (a sample of every 61st word).
 */
static const unsigned char digits[11][7] = {	/* 5x7, one byte per row, bit 4 = leftmost column */
	{0x0e,0x11,0x13,0x15,0x19,0x11,0x0e}, {0x04,0x0c,0x04,0x04,0x04,0x04,0x0e}, {0x0e,0x11,0x01,0x02,0x04,0x08,0x1f},
	{0x1f,0x02,0x04,0x02,0x01,0x11,0x0e}, {0x02,0x06,0x0a,0x12,0x1f,0x02,0x02}, {0x1f,0x10,0x1e,0x01,0x01,0x11,0x0e},
	{0x06,0x08,0x10,0x1e,0x11,0x11,0x0e}, {0x1f,0x01,0x02,0x04,0x08,0x08,0x08}, {0x0e,0x11,0x11,0x0e,0x11,0x11,0x0e},
	{0x0e,0x11,0x11,0x0f,0x01,0x02,0x0c}, {0x00,0x00,0x00,0x00,0x00,0x00,0x00},
};

static void draw_number(unsigned char *fb, unsigned stride, unsigned v)
{
	enum { S = 5, X0 = 24, Y0 = 90 };	/* scale, top-left position (below the panel's rounded corner) */
	char t[8];
	int n = snprintf(t, sizeof(t), "%2u", v > 99 ? 99 : v);
	for (unsigned y = Y0 - S; y < Y0 + 8 * S; y++)	/* dark box behind the digits */
		for (unsigned x = X0 - S; x < X0 + (unsigned)n * 6 * S; x++)
			*(unsigned *)(fb + (size_t)y * stride + x * 4) = 0xff000000;
	for (int i = 0; i < n; i++) {
		const unsigned char *g = digits[t[i] == ' ' ? 10 : t[i] - '0'];
		for (unsigned r = 0; r < 7; r++)
			for (unsigned c = 0; c < 5; c++)
				if (g[r] & (0x10 >> c))
					for (unsigned dy = 0; dy < S; dy++)
						for (unsigned dx = 0; dx < S; dx++)
							*(unsigned *)(fb + (size_t)(Y0 + r * S + dy) * stride + (X0 + (i * 6 + c) * S + dx) * 4) = 0xff00ff00;
	}
}

int main(int argc, char **argv)
{
	enum { W = 1080, H = 2160, PITCH = W * 4 };
	static unsigned char buf[PITCH * H];
	struct fb_fix_screeninfo fix;
	struct fb_var_screeninfo var;
	int fb = open("/dev/fb0", O_RDWR);

	if (fb < 0 || ioctl(fb, FBIOGET_FSCREENINFO, &fix) || ioctl(fb, FBIOGET_VSCREENINFO, &var)) {
		perror("fb0");
		return 1;
	}
	unsigned rows = var.yres < H ? var.yres : H, n = var.xres < W ? var.xres : W;
	/*
	 * Written with pwrite, not through a mapping: the DRM fbdev emulation pushes a write() to a command-mode panel at once (it marks the damage),
	 * while stores into the mmap reached /dev/fb0's memory but never the glass (test hosted23).
	 */
	static unsigned char frame[16 << 20];
	if ((size_t)fix.line_length * rows > sizeof(frame)) {
		fprintf(stderr, "fb0 too large\n");
		return 1;
	}
	const char *fpsenv = getenv("FPS");
	int show = !fpsenv || strcmp(fpsenv, "0");
	unsigned long long last_sum = 0;
	unsigned frames = 0, fps = 0;
	struct timespec t0;
	clock_gettime(CLOCK_MONOTONIC, &t0);
	for (;;) {
		int src = open(argc > 1 ? argv[1] : "/tmp/xnufb", O_RDONLY);
		if (src >= 0) {
			if (pread(src, buf, sizeof(buf), 0) == (ssize_t)sizeof(buf)) {
				for (unsigned y = 0; y < rows; y++)
					memcpy(frame + (size_t)y * fix.line_length, buf + (size_t)y * PITCH, n * 4);
				unsigned long long sum = 0;
				for (size_t i = 0; i < sizeof(buf) / 4; i += 61)
					sum = sum * 31 + ((const unsigned *)buf)[i];
				if (sum != last_sum) {
					frames++;
					last_sum = sum;
				}
				struct timespec t;
				clock_gettime(CLOCK_MONOTONIC, &t);
				if ((t.tv_sec - t0.tv_sec) * 1000000000LL + (t.tv_nsec - t0.tv_nsec) >= 1000000000LL) {
					fps = frames;
					frames = 0;
					t0 = t;
				}
				if (show)
					draw_number(frame, fix.line_length, fps);
				if (pwrite(fb, frame, (size_t)fix.line_length * rows, 0) < 0)
					perror("pwrite fb0");
			}
			close(src);
		}
		usleep(30000);
	}
}
