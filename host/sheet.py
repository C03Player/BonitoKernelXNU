#!/usr/bin/env python3
"""Contact sheets of uitour.py's screenshots (six side by side at a quarter size): sheet.py DIR"""
import glob, struct, sys, zlib


def load(p):
    d = open(p, 'rb').read()
    i, idat = 8, b''
    while i < len(d):
        n = struct.unpack('>I', d[i:i + 4])[0]
        if d[i + 4:i + 8] == b'IDAT':
            idat += d[i + 8:i + 8 + n]
        i += 12 + n
    r = zlib.decompress(idat)
    return [r[y * 3241 + 1:(y + 1) * 3241] for y in range(0, 2160, 4)]


files = sorted(glob.glob(sys.argv[1] + '/[0-9]*.png'))
chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
for k in range(0, len(files), 6):
    imgs = [load(f) for f in files[k:k + 6]]
    w = 270 * len(imgs) + 10 * (len(imgs) - 1)
    rows = bytearray()
    for y in range(540):
        rows += b'\0' + (b'\xff\0\xff' * 10).join(b''.join(im[y][x * 3:x * 3 + 3] for x in range(0, 1080, 4)) for im in imgs)
    out = '%s/sheet%d.png' % (sys.argv[1], k // 6)
    with open(out, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, 540, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(bytes(rows))) + chunk(b'IEND', b''))
    print(out, ' '.join(f.rsplit('/', 1)[1] for f in files[k:k + 6]))
