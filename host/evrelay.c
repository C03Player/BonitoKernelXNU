/*
 * evrelay OUT: Linux input events for the hosted system. Reads every /dev/input/event* device with a touchscreen (ABS_MT_POSITION_X) or the
 * power and volume keys, and appends 8-byte records (u16 type, u16 code, s32 value: struct linux64_input_event) to OUT, which xnu.ko reads
 * (input_in=OUT). Touch coordinates are scaled to the 1080x2160 panel.
 */
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define BIT(a, n) ((a)[(n) / 8] & (1 << ((n) % 8)))
struct rec { uint16_t type, code; int32_t value; };

static struct pollfd p[16];
static int maxx[16], maxy[16], n;
static unsigned long long seen;	/* event node numbers already examined */

/* open the touchscreens and key devices not seen yet (drivers can register theirs after this program starts) */
static void scan(void)
{
	for (int i = 0; i < 32 && n < 16; i++) {
		char path[32];
		unsigned char abs[ABS_MAX / 8 + 1] = {0}, key[KEY_MAX / 8 + 1] = {0};
		if (seen & (1ULL << i))
			continue;
		snprintf(path, sizeof(path), "/dev/input/event%d", i);
		int fd = open(path, O_RDONLY);
		if (fd < 0)
			continue;
		seen |= 1ULL << i;
		ioctl(fd, EVIOCGBIT(EV_ABS, sizeof(abs)), abs);
		ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(key)), key);
		int touch = BIT(abs, ABS_MT_POSITION_X), keys = BIT(key, KEY_POWER) || BIT(key, KEY_VOLUMEUP) || BIT(key, KEY_VOLUMEDOWN);
		char name[64] = "?";
		ioctl(fd, EVIOCGNAME(sizeof(name)), name);
		if (!touch && !keys) {
			printf("%s: %s (not used)\n", path, name);
			fflush(stdout);
			close(fd);
			continue;
		}
		struct input_absinfo ax = {0}, ay = {0};
		if (touch) {
			ioctl(fd, EVIOCGABS(ABS_MT_POSITION_X), &ax);
			ioctl(fd, EVIOCGABS(ABS_MT_POSITION_Y), &ay);
		}
		printf("%s: %s%s%s, x max %d, y max %d\n", path, name, touch ? " touch" : "", keys ? " keys" : "", ax.maximum, ay.maximum);
		fflush(stdout);
		maxx[n] = ax.maximum > 0 ? ax.maximum : 1079;
		maxy[n] = ay.maximum > 0 ? ay.maximum : 2159;
		p[n].fd = fd;
		p[n++].events = POLLIN;
	}
}

int main(int argc, char **argv)
{
	int out = open(argc > 1 ? argv[1] : "/tmp/xnuinput", O_WRONLY | O_CREAT | O_APPEND, 0600);

	if (out < 0) {
		perror("out");
		return 1;
	}
	scan();
	for (;;) {
		if (poll(p, n, 2000) <= 0) {
			scan();
			continue;
		}
		for (int i = 0; i < n; i++) {
			struct input_event ev[64];
			if (!(p[i].revents & POLLIN))
				continue;
			ssize_t got = read(p[i].fd, ev, sizeof(ev));
			struct rec r[64];
			int m = 0;
			for (int j = 0; j < got / (ssize_t)sizeof(ev[0]); j++) {
				int v = ev[j].value;
				if (ev[j].type == EV_ABS && ev[j].code == ABS_MT_POSITION_X)
					v = (int)((long long)v * 1079 / maxx[i]);
				else if (ev[j].type == EV_ABS && ev[j].code == ABS_MT_POSITION_Y)
					v = (int)((long long)v * 2159 / maxy[i]);
				r[m++] = (struct rec){ ev[j].type, ev[j].code, v };
			}
			if (m && write(out, r, m * sizeof(r[0])) < 0)
				perror("write");
		}
	}
}
