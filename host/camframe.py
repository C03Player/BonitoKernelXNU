#!/usr/bin/env python3
"""The newest frame of a camera file (host/camfile.h, a copy of the phone's /tmp/xnucam) as a PNG: camframe.py FILE OUT.png"""
import struct, sys, zlib

d = open(sys.argv[1], 'rb').read()
magic, seq, slot, w, h, camera = struct.unpack_from('<6I', d, 4096)
assert magic == 0x464d4143, 'no camera file state'
at = 8192 + slot * 0x400000
px = d[at:at + w * h * 4]
raw = b''.join(b'\0' + b''.join(px[i + 2:i + 3] + px[i + 1:i + 2] + px[i:i + 1] for i in range(y * w * 4, (y + 1) * w * 4, 4)) for y in range(h))
chunk = lambda t, b: struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b))
open(sys.argv[2], 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
                              chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
print('frame %d of camera %d, %dx%d: %s' % (seq, camera, w, h, sys.argv[2]))
