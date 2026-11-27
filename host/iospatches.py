#!/usr/bin/env python3
"""The patches to iOS's own code that the hosted system needs, and the list host/iospatch.c applies: iospatches.py DSC_DIR OUT [ROOT_IMAGE]

DSC_DIR: the dyld shared cache of the iOS on the phone (local only: Apple's code is never committed, the list is generated for each image).
ROOT_IMAGE: a copy of the root disk, to tell the phone where to look (optional; found once and kept in OUT.hint).

A changed page no longer matches its hash in the cache file's code signature, and a process that touches such a page loses its code
signature's validity (SpringBoard then aborts in the privacy checks). So the hash in the signature is replaced as well; the hosted kernel's
AMFI accepts the changed signature.
"""
import hashlib, mmap, os, struct, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../bonito/tools'))
from dsc import DSC

PATCHES = [
    # (unslid address, original instruction, replacement, why)
    # -[UIKeyboard setFrame:] reloads the keyboard when the new size differs from the view's, and a reload goes back to the letters. On this
    # 360-point screen the view starts 320 points wide, so every switch to "123" was undone and the keys sat 20 points to the right.
    # "fcmp d2, d11" (old width, new width) becomes "fcmp d11, d11": only a change of height reloads.
    (0x18911c494, 0x1e6b2040, 0x1e6b2160, 'keyboard: 123 key, shifted keys'),
]


def locate(cache, va):
    """(cache file, offset in it) of an address"""
    for a, size, offset, path in cache.maps:
        if a <= va < a + size:
            return path, offset + va - a
    sys.exit('0x%x: not in the shared cache' % va)


def page_hash(path, offset):
    """(file offset of the code directory's hash of the page holding offset, page offset, page size)"""
    with open(path, 'rb') as f:
        header = f.read(0x40)
        start, size = struct.unpack_from('<QQ', header, 0x28)
        f.seek(start)
        blob = f.read(size)
    count = struct.unpack_from('>I', blob, 8)[0]
    found = []
    for i in range(count):
        at = struct.unpack_from('>I', blob, 16 + 8 * i)[0]
        if struct.unpack_from('>I', blob, at)[0] != 0xfade0c02:	# CodeDirectory
            continue
        hashes = struct.unpack_from('>I', blob, at + 16)[0]
        length, kind, _, shift = struct.unpack_from('>4B', blob, at + 36)
        if kind != 2 or length != 32:
            sys.exit('%s: a code directory that is not SHA-256' % path)
        found.append((start + at + hashes + (offset >> shift) * length, offset >> shift << shift, 1 << shift))
    if len(found) != 1:
        sys.exit('%s: %d code directories, one expected' % (path, len(found)))
    return found[0]


def main():
    d, out = sys.argv[1:3]
    image = sys.argv[3] if len(sys.argv) > 3 else None
    cache = DSC(d)
    hints = {}
    if os.path.exists(out + '.hint'):
        hints = dict((k, int(v, 0)) for k, v in (l.split() for l in open(out + '.hint')))

    def search(sig):
        key = sig.hex()
        if key not in hints and image and os.path.exists(image):
            with open(image, 'rb') as f:
                hints[key] = mmap.mmap(f.fileno(), 0, prot=mmap.PROT_READ).find(sig)
        return hints.get(key, -1)

    lines = []
    pages = {}	# (file, hash offset) -> (page offset, page size, [(offset, replacement)], offset and hint of one instruction)
    for va, old, new, why in PATCHES:
        sig = cache.read(va - 12, 24)
        if struct.unpack_from('<I', sig, 12)[0] != old:
            sys.exit('%s: 0x%x holds another instruction: not the iOS this patch was written for' % (why, va))
        path, offset = locate(cache, va)
        hint = search(sig)
        lines.append('%d %s 12 %s\n' % (hint, sig.hex(), struct.pack('<I', new).hex()))
        entry, page, size = page_hash(path, offset)
        pages.setdefault((path, entry), (page, size, [], offset - 12, hint))[2].append((offset, struct.pack('<I', new)))
    for (path, entry), (page, size, changes, near, near_hint) in pages.items():
        with open(path, 'rb') as f:
            f.seek(page)
            data = bytearray(f.read(size))
            f.seek(entry)
            old = f.read(32)
        if hashlib.sha256(data).digest() != old:
            sys.exit('%s: the signature does not match the page at 0x%x' % (path, page))
        for offset, word in changes:
            data[offset - page:offset - page + 4] = word
        # the file is normally in one piece on the disk, so the hash sits at the same distance from the instruction
        hint = near_hint + entry - near if near_hint >= 0 else -1
        if hint >= 0 and image and os.path.exists(image):
            with open(image, 'rb') as f:
                f.seek(hint)
                if f.read(32) != old:
                    hint = -1
        if hint < 0:
            hint = search(old)
        lines.append('%d %s 0 %s\n' % (hint, old.hex(), hashlib.sha256(data).hexdigest()))
    open(out, 'w').writelines(lines)
    open(out + '.hint', 'w').writelines('%s %d\n' % kv for kv in hints.items() if kv[1] >= 0)
    print('%s: %d changes' % (out, len(lines)))


if __name__ == '__main__':
    main()
