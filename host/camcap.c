/*
 * camcap: raw frames from the phone's cameras through Linux's qcom-camss (modules loaded: host/initramfs/cam-up).
 *
 *   camcap list                                       the media graph: entities, pads, links
 *   camcap shot imx363|imx355 OUT [-n FRAMES] [-e EXPOSURE_LINES] [-g ANALOGUE_GAIN] [-d DIGITAL_GAIN]
 *
 * "shot" connects sensor -> CSIPHY (fixed) -> CSID -> VFE raw dump interface -> video node, gives every pad the sensor's format,
 * lets FRAMES frames pass (default 8, for the controls to take effect) and writes the last one to OUT, then prints
 * "width height bytesperline fourcc". The data are the sensor's Bayer samples (10 bit packed: 4 pixels in 5 bytes); host/camraw.py
 * turns them into a picture.
 */
#include <errno.h>
#include <fcntl.h>
#include <glob.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>
#include <linux/media.h>
#include <linux/v4l2-subdev.h>
#include <linux/videodev2.h>

#define MAXE 128
#define MAXL 32

static int media = -1;
static struct media_entity_desc ent[MAXE];
static int nent;

static void die(const char *what)
{
	fprintf(stderr, "camcap: %s: %s\n", what, strerror(errno));
	exit(1);
}

static void open_graph(void)
{
	glob_t g;

	if (glob("/dev/media*", 0, NULL, &g) != 0)
		die("no /dev/media*");
	for (size_t i = 0; i < g.gl_pathc && media < 0; i++) {
		struct media_device_info info;
		int fd = open(g.gl_pathv[i], O_RDWR);

		if (fd >= 0 && ioctl(fd, MEDIA_IOC_DEVICE_INFO, &info) == 0 && strstr(info.driver, "camss"))
			media = fd;
		else if (fd >= 0)
			close(fd);
	}
	globfree(&g);
	if (media < 0)
		die("no camss media device");
	for (__u32 id = MEDIA_ENT_ID_FLAG_NEXT; nent < MAXE; id = ent[nent++].id | MEDIA_ENT_ID_FLAG_NEXT) {
		memset(&ent[nent], 0, sizeof(ent[nent]));
		ent[nent].id = id;
		if (ioctl(media, MEDIA_IOC_ENUM_ENTITIES, &ent[nent]) != 0)
			break;
	}
}

static int links_of(const struct media_entity_desc *e, struct media_link_desc *links)
{
	static struct media_pad_desc pads[64];
	struct media_links_enum q = { .entity = e->id, .pads = pads, .links = links };

	if (e->links > MAXL || e->pads > 64 || ioctl(media, MEDIA_IOC_ENUM_LINKS, &q) != 0)
		return 0;
	return e->links;
}

static struct media_entity_desc *by_id(__u32 id)
{
	for (int i = 0; i < nent; i++)
		if (ent[i].id == id)
			return &ent[i];
	return NULL;
}

static struct media_entity_desc *by_name(const char *prefix)
{
	for (int i = 0; i < nent; i++)
		if (strncmp(ent[i].name, prefix, strlen(prefix)) == 0)
			return &ent[i];
	return NULL;
}

/* the device node of an entity: the /dev node with its numbers */
static int open_node(const struct media_entity_desc *e)
{
	static const char *pattern[] = { "/dev/v4l-subdev*", "/dev/video*" };

	for (int p = 0; p < 2; p++) {
		glob_t g;

		if (glob(pattern[p], 0, NULL, &g) != 0)
			continue;
		for (size_t i = 0; i < g.gl_pathc; i++) {
			struct stat st;

			if (stat(g.gl_pathv[i], &st) == 0 && major(st.st_rdev) == e->dev.major && minor(st.st_rdev) == e->dev.minor) {
				int fd = open(g.gl_pathv[i], O_RDWR);

				globfree(&g);
				if (fd < 0)
					die(e->name);
				return fd;
			}
		}
		globfree(&g);
	}
	fprintf(stderr, "camcap: no device node for %s\n", e->name);
	exit(1);
}

static void list(void)
{
	struct media_link_desc l[MAXL];

	for (int i = 0; i < nent; i++) {
		int n = links_of(&ent[i], l);

		printf("%s (%u pads, dev %u:%u)\n", ent[i].name, ent[i].pads, ent[i].dev.major, ent[i].dev.minor);
		for (int k = 0; k < n; k++) {
			struct media_entity_desc *to = by_id(l[k].sink.entity);

			printf("  pad %u -> %s pad %u%s%s\n", l[k].source.index, to ? to->name : "?", l[k].sink.index,
			    l[k].flags & MEDIA_LNK_FL_ENABLED ? " [on]" : "", l[k].flags & MEDIA_LNK_FL_IMMUTABLE ? " [fixed]" : "");
		}
	}
}

/* switches on the link from e's source pad to the entity "to"; every other changeable link into that sink pad goes off */
static void connect(const struct media_entity_desc *e, const struct media_entity_desc *to)
{
	struct media_link_desc l[MAXL], other[MAXL];
	int n = links_of(e, l);

	for (int k = 0; k < n; k++) {
		if (l[k].sink.entity != to->id)
			continue;
		for (int i = 0; i < nent; i++) {
			int m = links_of(&ent[i], other);

			for (int j = 0; j < m; j++) {
				if (other[j].sink.entity == to->id && other[j].sink.index == l[k].sink.index && ent[i].id != e->id &&
				    (other[j].flags & MEDIA_LNK_FL_ENABLED) && !(other[j].flags & MEDIA_LNK_FL_IMMUTABLE)) {
					other[j].flags &= ~MEDIA_LNK_FL_ENABLED;
					if (ioctl(media, MEDIA_IOC_SETUP_LINK, &other[j]) != 0)
						die("link off");
				}
			}
		}
		if (!(l[k].flags & (MEDIA_LNK_FL_ENABLED | MEDIA_LNK_FL_IMMUTABLE))) {
			l[k].flags |= MEDIA_LNK_FL_ENABLED;
			if (ioctl(media, MEDIA_IOC_SETUP_LINK, &l[k]) != 0)
				die("link on");
		}
		return;
	}
	fprintf(stderr, "camcap: no link from %s to %s\n", e->name, to->name);
	exit(1);
}

static void set_format(const struct media_entity_desc *e, int pad, struct v4l2_mbus_framefmt *f)
{
	struct v4l2_subdev_format s = { .which = V4L2_SUBDEV_FORMAT_ACTIVE, .pad = pad, .format = *f };
	int fd = open_node(e);

	if (ioctl(fd, VIDIOC_SUBDEV_S_FMT, &s) != 0)
		die(e->name);
	if (s.format.code != f->code || s.format.width != f->width || s.format.height != f->height)
		fprintf(stderr, "camcap: %s pad %d took %ux%u code 0x%x\n", e->name, pad, s.format.width, s.format.height, s.format.code);
	close(fd);
}

static __u32 fourcc_of(__u32 code)
{
	switch (code) {
	case MEDIA_BUS_FMT_SBGGR10_1X10: return V4L2_PIX_FMT_SBGGR10P;
	case MEDIA_BUS_FMT_SGBRG10_1X10: return V4L2_PIX_FMT_SGBRG10P;
	case MEDIA_BUS_FMT_SGRBG10_1X10: return V4L2_PIX_FMT_SGRBG10P;
	case MEDIA_BUS_FMT_SRGGB10_1X10: return V4L2_PIX_FMT_SRGGB10P;
	}
	fprintf(stderr, "camcap: sensor format 0x%x is not 10-bit Bayer\n", code);
	exit(1);
}

static void control(int fd, __u32 id, long value, const char *name)
{
	struct v4l2_queryctrl q = { .id = id };
	struct v4l2_control c = { .id = id };

	if (ioctl(fd, VIDIOC_QUERYCTRL, &q) != 0) {
		fprintf(stderr, "camcap: no control %s\n", name);
		return;
	}
	c.value = value < q.minimum ? q.minimum : value > q.maximum ? q.maximum : value;
	if (ioctl(fd, VIDIOC_S_CTRL, &c) != 0)
		fprintf(stderr, "camcap: %s: %s\n", name, strerror(errno));
	else
		fprintf(stderr, "camcap: %s %d (%d..%d)\n", name, c.value, q.minimum, q.maximum);
}

static void shot(const char *sensor_name, const char *out, int frames, long exposure, long gain, long dgain)
{
	struct media_entity_desc *sensor = by_name(sensor_name), *phy, *csid, *vfe, *video;
	struct media_link_desc l[MAXL];
	struct v4l2_subdev_format sf = { .which = V4L2_SUBDEV_FORMAT_ACTIVE, .pad = 0 };
	char name[32];
	int n, port = -1, sfd, vfd;

	if (!sensor)
		die(sensor_name);
	n = links_of(sensor, l);
	for (int k = 0; k < n; k++) {
		struct media_entity_desc *to = by_id(l[k].sink.entity);

		if (to && sscanf(to->name, "msm_csiphy%d", &port) == 1)
			break;
	}
	if (port < 0)
		die("the sensor feeds no CSIPHY");
	snprintf(name, sizeof(name), "msm_csiphy%d", port);
	phy = by_name(name);
	/* one CSID and one raw interface of VFE 0 are enough for one camera at a time */
	csid = by_name("msm_csid0");
	vfe = by_name("msm_vfe0_rdi0");
	video = by_name("msm_vfe0_video0");
	if (!phy || !csid || !vfe || !video) {
		errno = ENOENT;
		die("camss entities");
	}
	connect(phy, csid);
	connect(csid, vfe);
	sfd = open_node(sensor);
	if (ioctl(sfd, VIDIOC_SUBDEV_G_FMT, &sf) != 0)
		die("sensor format");
	set_format(phy, 0, &sf.format);
	set_format(csid, 0, &sf.format);
	set_format(csid, 1, &sf.format);
	set_format(vfe, 0, &sf.format);
	if (exposure >= 0)
		control(sfd, V4L2_CID_EXPOSURE, exposure, "exposure");
	if (gain >= 0)
		control(sfd, V4L2_CID_ANALOGUE_GAIN, gain, "analogue gain");
	if (dgain >= 0)
		control(sfd, V4L2_CID_DIGITAL_GAIN, dgain, "digital gain");

	vfd = open_node(video);
	struct v4l2_format f = { .type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE };
	f.fmt.pix_mp.width = sf.format.width;
	f.fmt.pix_mp.height = sf.format.height;
	f.fmt.pix_mp.pixelformat = fourcc_of(sf.format.code);
	f.fmt.pix_mp.num_planes = 1;
	if (ioctl(vfd, VIDIOC_S_FMT, &f) != 0)
		die("video format");

	struct v4l2_requestbuffers req = { .count = 4, .type = f.type, .memory = V4L2_MEMORY_MMAP };
	void *map[4];
	size_t len[4];

	if (ioctl(vfd, VIDIOC_REQBUFS, &req) != 0)
		die("buffers");
	for (unsigned i = 0; i < req.count && i < 4; i++) {
		struct v4l2_plane plane = { 0 };
		struct v4l2_buffer b = { .index = i, .type = f.type, .memory = V4L2_MEMORY_MMAP, .length = 1, .m.planes = &plane };

		if (ioctl(vfd, VIDIOC_QUERYBUF, &b) != 0)
			die("query buffer");
		len[i] = plane.length;
		map[i] = mmap(NULL, len[i], PROT_READ | PROT_WRITE, MAP_SHARED, vfd, plane.m.mem_offset);
		if (map[i] == MAP_FAILED || ioctl(vfd, VIDIOC_QBUF, &b) != 0)
			die("map buffer");
	}
	int type = f.type;
	if (ioctl(vfd, VIDIOC_STREAMON, &type) != 0)
		die("stream on");
	for (int got = 0; got < frames; got++) {
		struct pollfd p = { .fd = vfd, .events = POLLIN };
		struct v4l2_plane plane = { 0 };
		struct v4l2_buffer b = { .type = f.type, .memory = V4L2_MEMORY_MMAP, .length = 1, .m.planes = &plane };

		if (poll(&p, 1, 3000) <= 0) {
			errno = ETIMEDOUT;
			die("no frame in 3 s");
		}
		if (ioctl(vfd, VIDIOC_DQBUF, &b) != 0)
			die("take frame");
		if (got == frames - 1) {
			FILE *o = fopen(out, "wb");
			size_t want = (size_t)f.fmt.pix_mp.plane_fmt[0].bytesperline * f.fmt.pix_mp.height;

			if (!o || fwrite(map[b.index], 1, want, o) != want || fclose(o) != 0)
				die(out);
			printf("%u %u %u %.4s\n", f.fmt.pix_mp.width, f.fmt.pix_mp.height, f.fmt.pix_mp.plane_fmt[0].bytesperline,
			    (char *)&f.fmt.pix_mp.pixelformat);
		} else if (ioctl(vfd, VIDIOC_QBUF, &b) != 0) {
			die("give frame back");
		}
	}
	ioctl(vfd, VIDIOC_STREAMOFF, &type);
}

int main(int argc, char **argv)
{
	long exposure = -1, gain = -1, dgain = -1;
	int frames = 8, opt;

	if (argc < 2)
		goto usage;
	open_graph();
	if (strcmp(argv[1], "list") == 0) {
		list();
		return 0;
	}
	if (strcmp(argv[1], "shot") != 0 || argc < 4)
		goto usage;
	optind = 4;
	while ((opt = getopt(argc, argv, "n:e:g:d:")) != -1) {
		long v = atol(optarg);

		if (opt == 'n')
			frames = v > 0 ? v : 1;
		else if (opt == 'e')
			exposure = v;
		else if (opt == 'g')
			gain = v;
		else if (opt == 'd')
			dgain = v;
		else
			goto usage;
	}
	shot(argv[2], argv[3], frames, exposure, gain, dgain);
	return 0;
usage:
	fprintf(stderr, "usage: camcap list | camcap shot SENSOR OUT [-n frames] [-e lines] [-g gain] [-d gain]\n");
	return 2;
}
