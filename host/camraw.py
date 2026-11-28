#!/usr/bin/env python3
"""A camcap frame as a PNG: camraw.py FRAME WIDTH HEIGHT BYTESPERLINE FOURCC OUT.png [ROTATE]

One output pixel per 2x2 Bayer cell, every second cell (a quarter of the sensor's width), stretched so that the 99.5th percentile is white
(the sensor's black level, 64 of 1023, taken off), gamma 1/2.2, grey-world white balance. Prints the raw levels, which say whether the
sensor saw light at all. ROTATE: 0, 90, 180 or 270 degrees clockwise. Camera pictures are private: keep them out of git.
"""
import struct, sys, zlib

path, w, h, bpl, fourcc, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6]
rotate = int(sys.argv[7]) if len(sys.argv) > 7 else 0
data = open(path, 'rb').read()
assert len(data) >= bpl * h, 'short frame'
order = {'pBAA': 'BGGR', 'pGAA': 'GBRG', 'pgAA': 'GRBG', 'pRAA': 'RGGB'}[fourcc]
step = 4		# output pixel every 4 sensor pixels (every second Bayer cell)


def sample(x, y):
    g = y * bpl + (x >> 2) * 5
    k = x & 3
    return data[g + k] << 2 | (data[g + 4] >> (2 * k)) & 3


rows, total, lo, hi, hist = [], [0, 0, 0], 1023, 0, [0] * 1024
for y in range(0, h - 1, step):
    row = []
    for x in range(0, w - 1, step):
        c = {'R': 0, 'G': 0, 'B': 0}
        for i, ch in enumerate(order):
            v = sample(x + (i & 1), y + (i >> 1))
            c[ch] += v
            hist[v] += 1
        p = (c['R'], c['G'] / 2, c['B'])
        row.append(p)
    rows.append(row)
count = sum(hist)
mean = sum(i * n for i, n in enumerate(hist)) / count


def percentile(q):
    acc = 0
    for i, n in enumerate(hist):
        acc += n
        if acc >= count * q:
            return i
    return 1023


print('raw levels (0..1023): min %d, mean %.1f, median %d, 99.5%% %d, max %d' %
      (percentile(0.0000001), mean, percentile(0.5), percentile(0.995), percentile(1.0)))
black = 64
white = max(percentile(0.995) - black, 16)
avg = [sum(max(p[k] - black, 0) for r in rows for p in r) / (len(rows) * len(rows[0])) for k in range(3)]
wb = [avg[1] / a if a > 0.5 else 1.0 for a in avg]
lut = [int(round(255 * (i / 1023) ** (1 / 2.2))) for i in range(1024)]
img = [[bytes(lut[min(1023, int(max(p[k] - black, 0) * wb[k] / white * 1023))] for k in range(3)) for p in r] for r in rows]
for _ in range(rotate // 90):
    img = [list(r) for r in zip(*img[::-1])]
raw = b''.join(b'\0' + b''.join(r) for r in img)
chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
open(out, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', len(img[0]), len(img), 8, 2, 0, 0, 0)) +
                      chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
print('%s: %dx%d' % (out, len(img[0]), len(img)))
