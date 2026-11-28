#!/usr/bin/env python3
"""Read iOS unified logs (*.tracev3) of the phone far enough to debug a daemon: which library logged what, with its text arguments.

  tracev3.py DSCDIR FILE... [--lib REGEX] [--grep REGEX]

DSCDIR holds the dyld shared cache of the same iOS (format strings are read from it, bonito/tools/dsc.py). Only entries whose format string
lives in the shared cache are resolved; others print as "(program) +offset". Numbers are listed after the format string in argument order,
not substituted into it; private values are not in the file. Files are on the iOS volume under /private/var/db/diagnostics (they are the
phone's own data: do not commit them). Format: as read by mandiant/UnifiedLogReader; only the fields needed here are decoded.
"""
import bisect, os, re, struct, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bonito', 'tools'))
from dsc import DSC

CHUNKSET, FIREHOSE = 0x600d, 0x6001
BASE = 0x180000000


def lz4_block(src, out):
    i, n = 0, len(src)
    while i < n:
        token = src[i]; i += 1
        lit = token >> 4
        if lit == 15:
            while True:
                b = src[i]; i += 1; lit += b
                if b != 255:
                    break
        out += src[i:i + lit]; i += lit
        if i >= n:
            break
        off = src[i] | src[i + 1] << 8; i += 2
        length = token & 15
        if length == 15:
            while True:
                b = src[i]; i += 1; length += b
                if b != 255:
                    break
        length += 4
        start = len(out) - off
        if off >= length:
            out += out[start:start + length]
        else:
            for k in range(length):
                out.append(out[start + k])


def unpack_chunkset(d):
    """Apple's LZ4 stream: bv41 (compressed) and bv4- (stored) blocks, ended by bv4$."""
    out, i = bytearray(), 0
    while i + 4 <= len(d):
        magic = d[i:i + 4]
        if magic == b'bv41':
            _, clen = struct.unpack_from('<II', d, i + 4)
            lz4_block(d[i + 12:i + 12 + clen], out)	# matches may reach into earlier blocks
            i += 12 + clen
        elif magic == b'bv4-':
            n, = struct.unpack_from('<I', d, i + 4)
            out += d[i + 8:i + 8 + n]
            i += 8 + n
        else:
            break
    return bytes(out)


def chunks(d):
    i = 0
    while i + 16 <= len(d):
        tag, _, n = struct.unpack_from('<IIQ', d, i)
        if tag == 0 or n > len(d) - i - 16:
            break
        yield tag, d[i + 16:i + 16 + n]
        i += 16 + n
        i = (i + 7) & ~7


def tracepoints(c):
    """(process id, time, activity type, flags, format string location, data) of one firehose chunk."""
    if len(c) < 32:
        return
    _, pid = struct.unpack_from('<QI', c, 0)
    public, = struct.unpack_from('<H', c, 16)
    base, = struct.unpack_from('<Q', c, 24)
    i, end = 32, min(len(c), 16 + public)
    while i + 24 <= end:
        kind, _, flags, loc, _, lo, hi, n = struct.unpack_from('<BBHIQIHH', c, i)
        if kind == 0:
            break
        yield pid, base + (lo | hi << 32), kind, flags, loc, c[i + 24:i + 24 + n]
        i = (i + 24 + n + 7) & ~7


def main():
    args = sys.argv[1:]
    opt = {}
    for k in ('--lib', '--grep'):
        if k in args:
            j = args.index(k); opt[k] = re.compile(args[j + 1], re.I); del args[j:j + 2]
    if len(args) < 2:
        raise SystemExit(__doc__)
    dsc = DSC(args[0])
    images = dsc.images()
    starts = [a for a, _ in images]
    cache = {}

    def fmt(addr):
        if addr not in cache:
            try:
                raw = dsc.read(addr, 400).split(b'\0')[0].decode('utf-8', 'replace')
            except KeyError:
                raw = None
            cache[addr] = raw
        return cache[addr]

    rows = []
    for path in args[1:]:
        data = open(path, 'rb').read()
        for tag, c in chunks(data):
            if tag != CHUNKSET:
                continue
            for t, inner in chunks(unpack_chunkset(c)):
                if t == FIREHOSE:
                    rows += tracepoints(inner)
    rows.sort(key=lambda r: r[1])
    t0 = rows[0][1] if rows else 0
    for pid, when, kind, flags, loc, d in rows:
        if kind != 4:	# plain log messages only
            continue
        lib, text = '(program)', '+0x%x' % loc
        if flags & 0xe in (0x4, 0xc) and not loc & 0x80000000:
            addr = BASE + loc
            if flags & 0x20 or flags & 0xe == 0xc:
                # the high bits of the offset follow the call-site identifier
                p = (8 if flags & 1 else 0) + (4 if flags & 0x100 else 0) + 4
                if p + 2 <= len(d):
                    high, = struct.unpack_from('<H', d, p)
                    if fmt(BASE + (high << 31) + loc) is not None:
                        addr = BASE + (high << 31) + loc
            s = fmt(addr)
            if s is not None:
                k = bisect.bisect_right(starts, addr) - 1
                lib, text = images[k][1].rsplit('/', 1)[-1] if k >= 0 else '?', s
        elif loc & 0x80000000:
            text = '%s'
        strings = [m.decode() for m in re.findall(rb'[\x20-\x7e\n\t]{3,}', d)]
        line = '%10.3f pid %-4d %-22s %s | %s' % ((when - t0) / 24e6, pid, lib, text.replace('\n', ' '), ' ; '.join(strings).replace('\n', ' '))
        if '--lib' in opt and not opt['--lib'].search(lib):
            continue
        if '--grep' in opt and not opt['--grep'].search(line):
            continue
        print(line[:4000])


if __name__ == '__main__':
    main()
