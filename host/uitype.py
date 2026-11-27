#!/usr/bin/env python3
"""Type on the hosted iOS's keyboard (lower-case letters, ".", space, "\\n" = the Go key) by injected touches: uitype.py TEXT

The keyboard must be up. Without the keyboard patch (docs/IOS-PATCHES.md) it can sit shifted right with its last column cut off; told apart
by a screenshot: where the "q" key starts.
"""
import os, subprocess, sys, tempfile, time, zlib, struct

here = os.path.dirname(os.path.abspath(__file__))
png = tempfile.mktemp(suffix='.png')
subprocess.run([sys.executable, here + '/fbshot.py', png, '/tmp/xnufb'], check=True, capture_output=True, timeout=90)
d, i, idat = open(png, 'rb').read(), 8, b''
os.unlink(png)
while i < len(d):
    n = struct.unpack('>I', d[i:i + 4])[0]
    if d[i + 4:i + 8] == b'IDAT':
        idat += d[i + 8:i + 8 + n]
    i += 12 + n
raw = zlib.decompress(idat)
pixel = lambda x, y: sum(raw[y * 3241 + 1 + x * 3:y * 3241 + 4 + x * 3]) // 3
shifted = pixel(30, 1340) < pixel(110, 1340) - 20      # background where the flush keyboard has its first key
dx = 60 if shifted else 0
rows = (('qwertyuiop', 53, 1379), ('asdfghjkl', 108, 1541), ('zxcvbnm', 216, 1703))
keys = {c: (x0 + 108 * k + dx, y) for row, x0, y in rows for k, c in enumerate(row)}
keys.update({'.': (823 + dx, 1866), ' ': (573 + dx, 1866), '\n': (min(985 + dx, 1060), 1866)})
for c in sys.argv[1].replace('\\n', '\n'):
    subprocess.run([sys.executable, here + '/touch.py', 'long', str(keys[c][0]), str(keys[c][1]), '70'], check=True, capture_output=True, timeout=90)
    time.sleep(0.8)
print('typed on the %s keyboard' % ('shifted' if shifted else 'flush'))
