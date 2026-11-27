#!/usr/bin/env python3
"""Device-tree properties iOS needs, for xnu.ko's `adtprops` parameter: mkadtprops.py OUT

The hosted device tree is built by xnu.ko; iOS userland (iPhone X, iPhone10,3 / D22AP) reads its identity from it. The values come from the direct port's
bonito/tools/mkadt.py (root identity, /chosen, /chosen/asmb, /defaults, and /product from the real D22AP tree in bonito/research, a local Apple file).
'xiaomi,sweet' matches the direct port's device-tree platform expert (hosted, it touches no hardware); the CPU nodes stay xnu.ko's.
Record: char node[32]; char name[32]; u32 length; value padded to 4 bytes.
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../bonito/tools'))
import mkadt

root = mkadt.build(seed=bytes(64))
name_of = lambda n: dict((k, v) for k, f, v in n.props)['name'].rstrip(b'\0').decode()
find = {}


def walk(n):
    find.setdefault(name_of(n), n)
    for c in n.children:
        walk(c)


walk(root)
cstr = mkadt.cstr
out = [('device-tree', 'compatible', cstr('D22AP') + cstr('iPhone10,3') + cstr('xiaomi,sweet') + cstr('AppleARM'))]
props = lambda node: {k: v for k, f, v in find[node].props}
for node, keys in (('device-tree', ('model', 'target-type', 'target-sub-type', 'manufacturer')),
                   ('chosen', ('boot-manifest-hash', 'crypto-hash-method', 'display-scale', 'unique-chip-id', 'chip-id', 'certificate-production-status',
                               'effective-production-status-ap', 'certificate-security-mode', 'effective-security-mode-sep', 'mac-address-wifi0',
                               'mac-address-bluetooth0', 'mac-address-ethernet0')),
                   ('asmb', ('lp-sip0', 'lp-sip1')),
                   ('defaults', ('no-effaceable-storage',))):
    p = props(node)
    out += [(node, k, p[k]) for k in keys]
if 'product' not in find:
    sys.exit('no /product node: bonito/research/ipsw-x/d22ap.adt is missing')
# CPUs: the direct port's CPU driver (SweetCPU, IONameMatch qcom,kryo470) registers them; xnu.ko writes name, reg (MPIDR) and state
for i in range(8):
    if 'cpu%d' % i in find:
        out += [('cpu%d' % i, k, v) for k, v in props('cpu%d' % i).items() if k not in ('name', 'AAPL,phandle', 'reg', 'state', 'timebase-frequency', 'cpu-id', 'cluster-core-id', 'l2-cache-id', 'clock-frequency')]
# ARTWORK_SUBTYPE overrides artwork-device-subtype for experiments (2340, tried 2026-11-27, makes iOS behave like a home-button phone:
# "Press home to open"). The iPhone X's own value fits the 360x720-point panel, keyboard included.
product = dict(props('product'))
if 'artwork-device-subtype' in product:
    product['artwork-device-subtype'] = struct.pack('<I', int(os.environ.get('ARTWORK_SUBTYPE', '2436')))
out += [('product', k, v) for k, v in product.items() if k not in ('name', 'AAPL,phandle')]
with open(sys.argv[1], 'wb') as f:
    for node, k, v in out:
        f.write(struct.pack('<32s32sI', node.encode(), k.encode(), len(v)) + v + b'\0' * (-len(v) & 3))
print('%s: %d properties' % (sys.argv[1], len(out)), file=sys.stderr)
