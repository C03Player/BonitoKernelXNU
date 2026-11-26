#!/usr/bin/env python3
"""Assemble the GPU test userland for the Linux host without chroot: Mesa Turnip from Debian trixie packages (unpacked as plain files)
plus vktest.c built with this machine's compiler.  Output: work/host/gpu/ -> mkboot.sh puts it at /gpu in the image.

  gpu-userland.py [DL_DIR]      needs: glslangValidator, libvulkan-dev, gcc, dpkg-deb; DL_DIR defaults to /usb/work/gpu-linux/dl
Each package is checked against the SHA256 in the Debian package index.
"""
import hashlib, lzma, os, re, shutil, subprocess, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DL = sys.argv[1] if len(sys.argv) > 1 else '/usb/work/gpu-linux/dl'
TREE = os.path.join(os.path.dirname(DL), 'tree')
OUT = os.path.join(ROOT, 'work/host/gpu')
MIRROR = 'http://deb.debian.org/debian/'
os.makedirs(DL, exist_ok=True)
if not os.path.exists(DL + '/Packages.xz'):
    urllib.request.urlretrieve(MIRROR + 'dists/trixie/main/binary-arm64/Packages.xz', DL + '/Packages.xz')
P = {}
for st in lzma.open(DL + '/Packages.xz', 'rt').read().split('\n\n'):
    d = dict(l.split(': ', 1) for l in st.split('\n') if ': ' in l and not l.startswith(' '))
    if 'Package' in d:
        P[d['Package']] = d
want, todo = set(), ['mesa-vulkan-drivers', 'libvulkan1', 'libc6']
while todo:
    n = todo.pop()
    if n in want or n not in P:
        continue
    want.add(n)
    todo += [re.split(r'[ (:]', alt.split('|')[0].strip())[0] for alt in P[n].get('Depends', '').split(',') if alt.strip()]
shutil.rmtree(TREE, ignore_errors=True)
os.makedirs(TREE)
for n in sorted(want):
    d = P[n]
    f = os.path.join(DL, os.path.basename(d['Filename']))
    if not os.path.exists(f) or hashlib.sha256(open(f, 'rb').read()).hexdigest() != d['SHA256']:
        urllib.request.urlretrieve(MIRROR + d['Filename'], f)
    assert hashlib.sha256(open(f, 'rb').read()).hexdigest() == d['SHA256'], 'bad checksum: ' + f
    subprocess.run(['dpkg-deb', '-x', f, TREE], check=True)
print('%d packages unpacked' % len(want))

# only the shared objects that the loader, the Turnip driver and vktest pull in
libs = {}
for base, _, files in os.walk(TREE):
    for f in files:
        if '.so' in f:
            libs.setdefault(f, os.path.join(base, f))


def needed(path):
    o = subprocess.run(['readelf', '-d', path], capture_output=True, text=True).stdout
    return re.findall(r'\(NEEDED\).*\[(.*?)\]', o)


take, todo = {}, ['libvulkan.so.1', 'libvulkan_freedreno.so', 'ld-linux-aarch64.so.1', 'libc.so.6', 'libm.so.6']
while todo:
    n = todo.pop()
    if n in take:
        continue
    assert n in libs, 'missing library ' + n
    take[n] = os.path.realpath(libs[n])
    if not take[n].startswith(TREE):   # absolute symlink inside the package tree
        take[n] = TREE + take[n]
    todo += needed(take[n])
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT + '/lib')
for n, p in take.items():
    shutil.copy(p, OUT + '/lib/' + n)
open(OUT + '/freedreno_icd.json', 'w').write('{"file_format_version":"1.0.1","ICD":{"library_path":"/gpu/lib/libvulkan_freedreno.so","api_version":"1.4.0"}}\n')

src = ROOT + '/bonito/userland/phone/turnip'
tmp = OUT + '/shaders'
os.makedirs(tmp)
with open(tmp + '/shaders.h', 'w') as h:
    for s, v in (('fill.comp', 'fill_comp'), ('tri.vert', 'tri_vert'), ('tri.frag', 'tri_frag')):
        subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.2', '--vn', v, '-o', tmp + '/' + v + '.h', src + '/shaders/' + s],
                       check=True, stdout=subprocess.DEVNULL)
        h.write(open(tmp + '/' + v + '.h').read())
subprocess.run(['gcc', '-O2', '-Wall', '-I', tmp, '-o', OUT + '/vktest', src + '/vktest.c', '-ldl'], check=True)
shutil.rmtree(tmp)
open(OUT + '/run', 'w').write('#!/bin/sh\n# /gpu/run: vktest on Turnip through the Vulkan loader\nmkdir -p /var/local\n'
    'VK_DRIVER_FILES=/gpu/freedreno_icd.json exec /gpu/lib/ld-linux-aarch64.so.1 --library-path /gpu/lib /gpu/vktest /gpu/lib/libvulkan.so.1\n')
os.chmod(OUT + '/run', 0o755)
print('ok:', OUT, sum(os.path.getsize(os.path.join(b, f)) for b, _, fs in os.walk(OUT) for f in fs) >> 20, 'MiB,', sorted(take))
