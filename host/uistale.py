#!/usr/bin/env python3
"""Repeat "scroll a list down and back to the top" and compare each screenshot with the first: stale content shows as a difference.

  uistale.py OUTDIR [ROUNDS]      Settings must be open at the top. Compared: y=560 to 2040 (below the status bar).
"""
import os, struct, subprocess, sys, time, zlib

here = os.path.dirname(os.path.abspath(__file__))
out, rounds = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 12
os.makedirs(out, exist_ok=True)


def touch(*a):
    subprocess.run([sys.executable, here + '/touch.py', *a], check=True, capture_output=True, timeout=90)


def shot(path):
    subprocess.run([sys.executable, here + '/fbshot.py', path, '/tmp/xnufb'], check=True, capture_output=True, timeout=90)
    d, i, idat = open(path, 'rb').read(), 8, b''
    while i < len(d):
        n = struct.unpack('>I', d[i:i + 4])[0]
        if d[i + 4:i + 8] == b'IDAT':
            idat += d[i + 8:i + 8 + n]
        i += 12 + n
    return zlib.decompress(idat)


def corrupt(ref, got):
    """Blocks (90 x 30 pixels) of got that no vertical shift of up to 2 pixels explains (a list can settle 1 pixel off)."""
    def block(img, x, y):
        return b''.join(img[r * 3241 + 1 + x * 3:r * 3241 + 1 + (x + 90) * 3] for r in range(y, y + 30))
    found = []
    for y in range(560, 2010, 30):
        for x in range(0, 1080, 90):
            b = block(got, x, y)
            if b != block(ref, x, y) and all(sum(abs(a - c) > 40 for a, c in zip(block(ref, x, y + dy)[1::3], b[1::3])) > 15
                                             for dy in (0, -1, 1, -2, 2)):
                found.append((x, y))
    return found


def to_top():
    for _ in range(3):
        touch('swipe', '540', '600', '540', '1900', '10')
        time.sleep(0.6)
    time.sleep(4)


to_top()
ref = shot(out + '/ref.png')
bad = 0
for r in range(rounds):
    for _ in range(2):
        touch('swipe', '540', '1600', '540', '400', '10')
        time.sleep(0.5)
    time.sleep(2)
    moved = shot(out + '/scrolled.png')
    if moved[560 * 3241:2040 * 3241] == ref[560 * 3241:2040 * 3241]:
        sys.exit('round %d: the screen did not change after scrolling (frozen?)' % r)
    to_top()
    got = shot('%s/%02d.png' % (out, r))
    if got[560 * 3241:2040 * 3241] == moved[560 * 3241:2040 * 3241]:
        sys.exit('round %d: the screen did not change on the way back (frozen?)' % r)
    blocks = corrupt(ref, got)
    if blocks:
        bad += 1
        print('round %d: %d wrong blocks, y %d-%d' % (r, len(blocks), min(y for _, y in blocks), max(y for _, y in blocks) + 29), flush=True)
    else:
        os.unlink('%s/%02d.png' % (out, r))
print('%d of %d rounds show wrong content' % (bad, rounds))
