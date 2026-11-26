#!/usr/bin/env python3
"""Screenshot of the phone's Linux framebuffer (what the screen shows, XRGB8888 1080x2160) as PNG, through psh.py: fbshot.py OUT.png [SOURCE]   (SOURCE: default /dev/fb0; /tmp/xnufb is the hosted system's own framebuffer)"""
import base64, gzip, os, struct, subprocess, sys, zlib

W, H = 1080, 2160
here = os.path.dirname(os.path.abspath(__file__))
env = dict(os.environ, PSH_TIMEOUT='60')
src = sys.argv[2] if len(sys.argv) > 2 else '/dev/fb0'
# /dev/fb0's rows are longer than the picture (its stride); /tmp/xnufb's are exactly 4320 bytes
cmd = 'P=4320; [ %s = /dev/fb0 ] && P=$(cat /sys/class/graphics/fb0/stride); echo P$P; dd if=%s bs=$P count=%d 2>/dev/null | gzip -1 | base64' % (src, src, H)
out = subprocess.run([sys.executable, here + '/psh.py', cmd], capture_output=True, env=env, timeout=90, check=True).stdout
pitch = int(out.split(b'P', 1)[1].split()[0])
out = out.split(b'\n', 1)[1] if out.startswith(b'P') else out[out.index(b'\n', out.index(b'P')) + 1:]
packed = gzip.decompress(base64.b64decode(b''.join(l for l in out.split() if l)))
raw = b''.join(packed[y * pitch:y * pitch + W * 4] for y in range(H))
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
