#!/usr/bin/env python3
"""Repeat "scroll a list down and back to the top" and compare each screenshot with the first: stale content shows as a difference.

  uistale.py OUTDIR [ROUNDS]      Settings must be open at the top. Compared: the rows between y=560 and y=2050 (below the status bar).
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
    to_top()
    got = shot('%s/%02d.png' % (out, r))
    diff = [y for y in range(560, 2050) if got[y * 3241:(y + 1) * 3241] != ref[y * 3241:(y + 1) * 3241]]
    if len(diff) > 3:
        bad += 1
        print('round %d: %d rows differ, y %d-%d' % (r, len(diff), diff[0], diff[-1]), flush=True)
    else:
        os.unlink('%s/%02d.png' % (out, r))
print('%d of %d rounds differ from the reference' % (bad, rounds))
