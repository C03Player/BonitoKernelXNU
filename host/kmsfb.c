/*
 * kmsfb: shows the hosted iOS framebuffer on the phone's panel without copying it. The framebuffer's physical pages (xnu.ko's fb_phys and
 * fb_bytes) become a dma-buf through fki's hostcall device, the display driver imports it and scans it out, and each tick asks for a panel
 * update (the panel is in command mode: it keeps its last frame until told). Replaces fbcopy, which copied every frame three times.
 *
 *   kmsfb [HZ]		updates per second (default 60)
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
#include <drm/drm_fourcc.h>
#include <drm/drm_mode.h>

struct xnu_hostcall_dmabuf { uint64_t pa, n; int32_t fd; uint32_t pad; };	/* hosted/fki-ko/fki_hostcall.c */
#define XNU_HOSTCALL_DMABUF _IOWR('X', 4, struct xnu_hostcall_dmabuf)

static void die(const char *what)
{
	fprintf(stderr, "kmsfb: %s: %s\n", what, strerror(errno));
	exit(1);
}

static uint64_t param(const char *name)
{
	char path[128];
	unsigned long long v = 0;
	snprintf(path, sizeof(path), "/sys/module/xnu/parameters/%s", name);
	FILE *f = fopen(path, "r");
	if (!f || fscanf(f, "%llu", &v) != 1)
		v = 0;
	if (f)
		fclose(f);
	return v;
}

int main(int argc, char **argv)
{
	int hz = argc > 1 ? atoi(argv[1]) : 60;
	uint64_t pa = 0, bytes = 0, width = 0, height = 0;
	for (int i = 0; i < 600 && !pa; i++) {	/* xnu.ko sets them while it loads */
		pa = param("fb_phys");
		if (!pa)
			usleep(100000);
	}
	bytes = param("fb_bytes");
	width = param("fb_width");
	height = param("fb_height");
	if (!pa || !bytes || !width || !height)
		die("xnu.ko has no framebuffer");

	uint64_t n = (bytes + 4095) / 4096, *pages = malloc(n * 8);
	for (uint64_t i = 0; i < n; i++)
		pages[i] = pa + i * 4096;
	int hc = open("/dev/xnu-hostcall", O_RDWR | O_CLOEXEC);
	if (hc < 0)
		die("/dev/xnu-hostcall");
	struct xnu_hostcall_dmabuf db = { .pa = (uintptr_t)pages, .n = n };
	if (ioctl(hc, XNU_HOSTCALL_DMABUF, &db))
		die("dma-buf of the framebuffer");
	close(hc);	/* the dma-buf lives on; the hostcall device is the GPU service's */

	int fd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
	if (fd < 0)
		die("/dev/dri/card0");
	ioctl(fd, DRM_IOCTL_SET_MASTER, 0);
	struct drm_prime_handle ph = { .fd = db.fd };
	if (ioctl(fd, DRM_IOCTL_PRIME_FD_TO_HANDLE, &ph))
		die("import");

	/* the connected connector, its first (preferred) mode, and a CRTC for it */
	struct drm_mode_card_res res = { 0 };
	uint32_t conns[16], crtcs[16], encs[16];
	if (ioctl(fd, DRM_IOCTL_MODE_GETRESOURCES, &res))
		die("resources");
	res.count_fbs = 0;
	res.count_connectors = res.count_connectors > 16 ? 16 : res.count_connectors;
	res.count_crtcs = res.count_crtcs > 16 ? 16 : res.count_crtcs;
	res.count_encoders = res.count_encoders > 16 ? 16 : res.count_encoders;
	res.connector_id_ptr = (uintptr_t)conns;
	res.crtc_id_ptr = (uintptr_t)crtcs;
	res.encoder_id_ptr = (uintptr_t)encs;
	if (ioctl(fd, DRM_IOCTL_MODE_GETRESOURCES, &res))
		die("resources");
	uint32_t conn = 0, crtc = 0;
	static struct drm_mode_modeinfo modes[64];
	for (uint32_t i = 0; i < res.count_connectors && !conn; i++) {
		struct drm_mode_get_connector c = { .connector_id = conns[i] };
		if (ioctl(fd, DRM_IOCTL_MODE_GETCONNECTOR, &c) || c.connection != 1 || !c.count_modes)
			continue;
		uint32_t encoders[8];
		c.count_modes = c.count_modes > 64 ? 64 : c.count_modes;
		c.count_encoders = c.count_encoders > 8 ? 8 : c.count_encoders;
		c.count_props = 0;
		c.modes_ptr = (uintptr_t)modes;
		c.encoders_ptr = (uintptr_t)encoders;
		if (ioctl(fd, DRM_IOCTL_MODE_GETCONNECTOR, &c))
			continue;
		struct drm_mode_get_encoder e = { .encoder_id = c.encoder_id ? c.encoder_id : encoders[0] };
		if (ioctl(fd, DRM_IOCTL_MODE_GETENCODER, &e))
			continue;
		crtc = e.crtc_id;
		for (uint32_t k = 0; k < res.count_crtcs && !crtc; k++)
			if (e.possible_crtcs & (1u << k))
				crtc = crtcs[k];
		conn = conns[i];
	}
	if (!conn || !crtc)
		die("no panel");

	struct drm_mode_fb_cmd2 fb = { .width = width, .height = height, .pixel_format = DRM_FORMAT_XRGB8888 };
	fb.handles[0] = ph.handle;
	fb.pitches[0] = bytes / height;
	if (ioctl(fd, DRM_IOCTL_MODE_ADDFB2, &fb))
		die("framebuffer");
	struct drm_mode_crtc set = { .crtc_id = crtc, .fb_id = fb.fb_id, .set_connectors_ptr = (uintptr_t)&conn, .count_connectors = 1,
				     .mode = modes[0], .mode_valid = 1 };
	if (ioctl(fd, DRM_IOCTL_MODE_SETCRTC, &set))
		die("mode set");
	fprintf(stderr, "kmsfb: %llux%llu at %#llx on connector %u, crtc %u, %d Hz\n", (unsigned long long)width,
		(unsigned long long)height, (unsigned long long)pa, conn, crtc, hz);

	struct timespec next, report;
	clock_gettime(CLOCK_MONOTONIC, &next);
	report = next;
	unsigned updates = 0, failed = 0;
	for (;;) {
		struct drm_mode_fb_dirty_cmd d = { .fb_id = fb.fb_id };
		if (ioctl(fd, DRM_IOCTL_MODE_DIRTYFB, &d))
			failed++;
		else
			updates++;
		next.tv_nsec += 1000000000 / (hz > 0 ? hz : 60);
		if (next.tv_nsec >= 1000000000) {
			next.tv_nsec -= 1000000000;
			next.tv_sec++;
		}
		struct timespec now;
		clock_gettime(CLOCK_MONOTONIC, &now);
		if (now.tv_sec > next.tv_sec || (now.tv_sec == next.tv_sec && now.tv_nsec > next.tv_nsec))
			next = now;
		else
			clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL);
		if (now.tv_sec - report.tv_sec >= 5) {
			fprintf(stderr, "kmsfb: %u panel updates, %u failed (%s) in 5 s\n", updates, failed, failed ? strerror(errno) : "-");
			updates = failed = 0;
			report = now;
		}
	}
}
