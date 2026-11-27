#!/usr/bin/env python3
"""Patch (or restore) one instruction of the running iOS in the phone's RAM: iospoke.py on|off ADDR INSN [ADDR:INSN ...]

ADDR: unslid shared cache address; INSN: the replacement (hex); the further pairs name neighbouring instructions that are already patched.
Needs host/sweetpoke/sweetpoke.ko as /tmp/sweetpoke.ko on the phone, and the page in memory (the code must have run). docs/IOS-PATCHES.md.
"""
import os, struct, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '../bonito/tools'))
from dsc import DSC
mode, va, new = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
b = bytearray(DSC(os.environ.get('DYLD', '/usb/work/dyld')).read(va - 12, 24)); old = struct.unpack_from('<I', b, 12)[0]
for a in sys.argv[4:]:	# VA:INSN: neighbouring instructions that are already patched
    v, i = (int(x, 16) for x in a.split(':'))
    if -12 <= v - va < 12: struct.pack_into('<I', b, v - va + 12, i)
if mode == 'off':
    struct.pack_into('<I', b, 12, new); new = old
# first look only: a signature of common code (a function's first instructions) matches hundreds of places, and patching them all wrecks
# the running system. One page can be mapped a few times, so a handful is accepted.
base = 'dmesg -c >/dev/null; insmod /tmp/sweetpoke.ko lo=0x100000000 hi=0x178000000 sig=%s at=12 insn=0x%x %s 2>/dev/null; dmesg | grep sweetpoke'
look = subprocess.run([sys.executable, here + '/psh.py', base % (b.hex(), new, 'dry=1')], capture_output=True, text=True, timeout=90).stdout
count = [int(x.split()[0]) for x in (l.split('sweetpoke: ')[-1] for l in look.splitlines()) if x.endswith('matches') and x.split()[0].isdigit()]
if not count or max(count) > 6:
    sys.exit('%s matches for this signature: nothing patched' % (max(count) if count else 'no'))
out = subprocess.run([sys.executable, here + '/psh.py', 'dmesg -c >/dev/null; insmod /tmp/sweetpoke.ko lo=0x100000000 hi=0x178000000 sig=%s at=12 insn=0x%x 2>/dev/null; dmesg | grep sweetpoke' % (b.hex(), new)], capture_output=True, text=True, timeout=90).stdout
print(out)
