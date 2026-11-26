#!/usr/bin/env python3
"""Screenshot of the phone's Linux framebuffer (what the screen shows, XRGB8888 1080x2160) as PNG, through psh.py: fbshot.py OUT.png"""
import base64, gzip, os, struct, subprocess, sys, zlib

W, H = 1080, 2160
here = os.path.dirname(os.path.abspath(__file__))
env = dict(os.environ, PSH_TIMEOUT='60')
out = subprocess.run([sys.executable, here + '/psh.py', 'dd if=/dev/fb0 bs=4320 count=%d 2>/dev/null | gzip -1 | base64' % H], capture_output=True, env=env, timeout=90, check=True).stdout
raw = gzip.decompress(base64.b64decode(b''.join(l for l in out.split() if l)))
assert len(raw) >= W * H * 4, 'short framebuffer: %d bytes' % len(raw)
rows = bytearray()
for y in range(H):
    line = raw[y * W * 4:(y + 1) * W * 4]
    rgb = bytearray(W * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = line[2::4], line[1::4], line[0::4]
    rows += b'\0' + rgb
chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
with open(sys.argv[1], 'wb') as f:
    f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(bytes(rows), 6)) + chunk(b'IEND', b''))
print('%s: %d distinct bytes in the framebuffer' % (sys.argv[1], len(set(raw[::4097]))))
