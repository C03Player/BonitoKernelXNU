/* fbcopy SRC: show the hosted system's framebuffer (SRC, a file of 1080x2160 rows of 4320 bytes that xnu.ko rewrites) on /dev/fb0, whose rows may be longer. 10 Hz. */
#include <fcntl.h>
#include <linux/fb.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

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
	static unsigned char frame[8 << 20];
	if ((size_t)fix.line_length * rows > sizeof(frame)) {
		fprintf(stderr, "fb0 too large\n");
		return 1;
	}
	for (;;) {
		int src = open(argc > 1 ? argv[1] : "/tmp/xnufb", O_RDONLY);
		if (src >= 0) {
			if (pread(src, buf, sizeof(buf), 0) == (ssize_t)sizeof(buf)) {
				for (unsigned y = 0; y < rows; y++)
					memcpy(frame + (size_t)y * fix.line_length, buf + (size_t)y * PITCH, n * 4);
				if (pwrite(fb, frame, (size_t)fix.line_length * rows, 0) < 0)
					perror("pwrite fb0");
			}
			close(src);
		}
		usleep(100000);
	}
}
