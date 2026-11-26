/* fbcopy SRC: show the hosted system's framebuffer (SRC, a file of 1080x2160 rows of 4320 bytes that xnu.ko rewrites) on /dev/fb0, whose rows may be longer. 10 Hz. */
#include <fcntl.h>
#include <linux/fb.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
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
	unsigned char *dst = mmap(0, fix.smem_len, PROT_READ | PROT_WRITE, MAP_SHARED, fb, 0);
	if (dst == MAP_FAILED) {
		perror("mmap");
		return 1;
	}
	for (;;) {
		int src = open(argc > 1 ? argv[1] : "/tmp/xnufb", O_RDONLY);
		if (src >= 0) {
			if (pread(src, buf, sizeof(buf), 0) == (ssize_t)sizeof(buf)) {
				for (unsigned y = 0; y < rows; y++)
					memcpy(dst + (size_t)y * fix.line_length, buf + (size_t)y * PITCH, n * 4);
				msync(dst, fix.smem_len, MS_ASYNC);
			}
			close(src);
		}
		usleep(100000);
	}
}
