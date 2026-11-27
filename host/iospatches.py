#!/usr/bin/env python3
"""The patches to iOS's code that the hosted system needs, and the list host/iospatch.c applies: iospatches.py DSC_DIR OUT [ROOT_IMAGE]

DSC_DIR: the dyld shared cache of the iOS on the phone (local only: Apple's code is never committed, the list is generated for each image).
ROOT_IMAGE: a copy of the root disk, to tell the phone where to look (optional; found once and kept in OUT.hint).

Patches to other binaries of the root disk (FILE_PATCHES) use a local copy in work/host/ios-files, read out of ROOT_IMAGE when missing.
The phone's copy can be newer than the image's (the direct port installed builds on the phone): then take the phone's file (mount a
read-only mapping of the volume's 33554432 sectors with -t hfsplus) and put the device offsets iospatch reports into OUT.hint.

A changed page no longer matches its hash in the file's code signature, and a process that touches such a page loses its code
signature's validity (SpringBoard then aborts in the privacy checks). So the hash in the signature is replaced as well; the hosted kernel's
AMFI accepts the changed signature.
"""
import hashlib, mmap, os, struct, subprocess, sys

import iosbright

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../bonito/tools'))
from dsc import DSC

PATCHES = [
    # (unslid address, original instruction, replacement, why)
    # -[UIKeyboard setFrame:] reloads the keyboard when the new size differs from the view's, and a reload goes back to the letters. On this
    # 360-point screen the view starts 320 points wide, so every switch to "123" was undone and the keys sat 20 points to the right.
    # "fcmp d2, d11" (old width, new width) becomes "fcmp d11, d11": only a change of height reloads.
    (0x18911c494, 0x1e6b2040, 0x1e6b2160, 'keyboard: 123 key, shifted keys'),
    # _BKSDisplayBrightnessSet's first instruction ("stp d9, d8, [sp, #-48]!") becomes a branch to the routine of host/iosbright.py
    (iosbright.FUNCTION, 0x6dbd23e9, 0x14000000 | (((iosbright.CAVE - iosbright.FUNCTION) >> 2) & 0x3ffffff), 'brightness: report the level'),
    # BKSDisplayBrightnessIsBrightnessLevelControlAvailable answers no without a backlight device, and Control Center then disables its
    # slider: its result ("cset w0, ne") becomes "mov w0, #1"
    (0x18dcf3234, 0x1a9f07e0, 0x52800020, 'brightness: Control Center slider'),
]


# code added to iOS: (unslid address, bytes, why); the place must be code that never runs
BLOCKS = [
    (iosbright.CAVE, iosbright.CODE, 'brightness: report the level (host/iosbright.py)'),
]

FILE_PATCHES = [
    # (file on the root disk, file offset, original instruction, replacement, why)
    # The Metal runtime of our plugin hands out an existing import again when memory is asked for at the same address and length. iOS frees
    # that memory and gets the address again with other pages while the old import lives: the GPU then read the old pages (rows of lists
    # showing other text, the clock in place of a label). "bl <find the live import>" becomes "mov x0, #0": always import anew.
    ('/System/Library/Extensions/SweetMetal2.bundle/SweetMetal2', 0x1504d4, 0x940a002b, 0xd2800000, 'stale text: no reuse of GPU imports'),
]


def local_copy(name, image, folder):
    """the local copy of a file of the root disk, read out of the image the first time"""
    path = os.path.join(folder, os.path.basename(name))
    if not os.path.exists(path):
        if not (image and os.path.exists(image)):
            sys.exit('%s: no local copy, and no root image to read it from' % path)
        os.makedirs(folder, exist_ok=True)
        reader = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../bonito/tools/hfsx.py')
        subprocess.run([sys.executable, reader, image, 'cat', name, path], check=True, stdout=subprocess.DEVNULL)
    return path


def on_disk(image, name, offset):
    """where byte `offset` of the root disk's file `name` is on the disk, or -1"""
    if not (image and os.path.exists(image)):
        return -1
    from hfsx import HFS, FileSource
    volume = HFS(FileSource(image))
    _, ident, record = volume.lookup(name)
    position = 0
    for start, count in volume._all_extents(record[88:168], ident)[1]:
        length = count * volume.bs
        if offset < position + length:
            return start * volume.bs + offset - position
        position += length
    return -1


def locate(cache, va):
    """(cache file, offset in it) of an address"""
    for a, size, offset, path in cache.maps:
        if a <= va < a + size:
            return path, offset + va - a
    sys.exit('0x%x: not in the shared cache' % va)


def page_hash(path, offset):
    """(file offset of the code directory's hash of the page holding offset, page offset, bytes the hash covers) of a shared cache file or a
    thin 64-bit Mach-O file"""
    with open(path, 'rb') as f:
        header = f.read(0x40)
        if header[:4] == b'\xcf\xfa\xed\xfe':	# Mach-O: the signature is named by its LC_CODE_SIGNATURE command
            count, total = struct.unpack_from('<II', header, 16)
            f.seek(32)
            commands, at, start = f.read(total), 0, 0
            for _ in range(count):
                command, length = struct.unpack_from('<II', commands, at)
                if command == 0x1d:
                    start, size = struct.unpack_from('<II', commands, at + 8)
                at += length
            if not start:
                sys.exit('%s: not signed' % path)
        else:
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
        limit = struct.unpack_from('>I', blob, at + 32)[0]
        page = offset >> shift << shift
        found.append((start + at + hashes + (offset >> shift) * length, page, min(1 << shift, limit - page)))
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

    def search(sig, scan=True):
        key = sig.hex()
        if key not in hints and scan and image and os.path.exists(image):
            with open(image, 'rb') as f:
                hints[key] = mmap.mmap(f.fileno(), 0, prot=mmap.PROT_READ).find(sig)
        return hints.get(key, -1)

    targets = []	# (file with the bytes, file name on the root disk, offset of the signature, its length, offset in it, replacement, why)
    for va, old, new, why in PATCHES:
        path, offset = locate(cache, va)
        if struct.unpack('<I', cache.read(va, 4))[0] != old:
            sys.exit('%s: 0x%x holds another instruction: not the iOS this patch was written for' % (why, va))
        targets.append((path, '/System/Library/Caches/com.apple.dyld/' + os.path.basename(path), offset - 12, 24, 12, struct.pack('<I', new), why))
    for va, code, why in BLOCKS:
        for at in range(0, len(code), 56):
            part = code[at:at + 56]
            path, offset = locate(cache, va + at)
            targets.append((path, '/System/Library/Caches/com.apple.dyld/' + os.path.basename(path), offset, len(part), 0, part, why))
    for name, offset, old, new, why in FILE_PATCHES:
        path = local_copy(name, image, os.path.join(os.path.dirname(os.path.abspath(out)), 'ios-files'))
        with open(path, 'rb') as f:
            f.seek(offset)
            if struct.unpack('<I', f.read(4))[0] != old:
                sys.exit('%s: %s holds another instruction at 0x%x: not the file this patch was written for' % (why, path, offset))
        targets.append((path, name, offset - 12, 24, 12, struct.pack('<I', new), why))

    lines = []
    pages = {}	# (file, hash offset) -> (page offset, bytes hashed, [(offset, replacement)], offset and hint of one instruction)
    for path, name, start, length, at, new, why in targets:
        with open(path, 'rb') as f:
            f.seek(start)
            sig = f.read(length)
        if sig.hex() not in hints:
            found = on_disk(image, name, start)
            if found >= 0 and image and os.pread(os.open(image, os.O_RDONLY), len(sig), found) == sig:
                hints[sig.hex()] = found
        hint = search(sig, scan=False)
        lines.append('%d %s %d %s\n' % (hint, sig.hex(), at, new.hex()))
        entry, page, size = page_hash(path, start + at)
        if (start + at + len(new) - 1) >= page + size:
            sys.exit('%s: a change that crosses a signed page' % why)
        pages.setdefault((path, entry), (page, size, [], start, hint, name))[2].append((start + at, new))
    for (path, entry), (page, size, changes, near, near_hint, name) in pages.items():
        with open(path, 'rb') as f:
            f.seek(page)
            data = bytearray(f.read(size))
            f.seek(entry)
            old = f.read(32)
        if hashlib.sha256(data).digest() != old:
            sys.exit('%s: the signature does not match the page at 0x%x' % (path, page))
        for offset, word in changes:
            data[offset - page:offset - page + len(word)] = word
        # the file is normally in one piece on the disk, so the hash sits at the same distance from the instruction
        hint = near_hint + entry - near if near_hint >= 0 else -1
        if hint >= 0 and image and os.path.exists(image):
            with open(image, 'rb') as f:
                f.seek(hint)
                if f.read(32) != old:
                    hint = -1
        if hint < 0 or old.hex() in hints:
            hint = search(old, scan=not name)
        lines.append('%d %s 0 %s\n' % (hint, old.hex(), hashlib.sha256(data).hexdigest()))
    open(out, 'w').writelines(lines)
    open(out + '.hint', 'w').writelines('%s %d\n' % kv for kv in hints.items() if kv[1] >= 0)
    print('%s: %d changes' % (out, len(lines)))


if __name__ == '__main__':
    main()
