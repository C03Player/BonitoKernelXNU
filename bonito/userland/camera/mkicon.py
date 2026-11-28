#!/usr/bin/env python3
"""mkicon.py OUT SIZE: the camera app's icon, a lens on grey, as a PNG"""
import struct, sys, zlib

n = int(sys.argv[2])


def pixel(x, y):
    r = ((x - n / 2) ** 2 + (y - n / 2) ** 2) ** 0.5 / n
    if r < 0.10:
        return (120, 160, 210)
    if r < 0.22:
        return (20, 24, 40)
    if r < 0.31:
        return (230, 230, 235)
    return (90, 92, 98)


raw = b''.join(b'\0' + b''.join(bytes(pixel(x + 0.5, y + 0.5)) for x in range(n)) for y in range(n))
chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
open(sys.argv[1], 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', n, n, 8, 2, 0, 0, 0)) +
                              chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
