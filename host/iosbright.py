"""The code added to iOS for the screen brightness (used by iospatches.py): bytes and addresses only, no assembler needed.

BKSDisplayBrightnessSet(float level, ...) begins with a branch to a small routine placed in code that never runs on a phone (the iPad-only
part of -[UIKeyboardLayoutStar showGestureKeyboardIntroductionIfNeeded]). The routine opens "/sweetbr" + the level's bits as eight hex
digits, which the hosted kernel prints (SWEET BRIGHTNESS), then runs the replaced instruction and goes back. Source: ASSEMBLY below;
`python3 host/iosbright.py` assembles it again and compares (needs aarch64-linux-gnu-as).
"""
FUNCTION = 0x18dcf3030		# _BKSDisplayBrightnessSet
CAVE = 0x1897eb6c0
ASSEMBLY = """
	stp x0, x1, [sp, #-64]!
	stp x2, x16, [sp, #16]
	ldr x9, 3f
	str x9, [sp, #32]
	fmov w10, s0
	add x11, sp, #40
	mov w12, #8
1:	lsr w13, w10, #28
	add w13, w13, #'0'
	cmp w13, #'9'
	b.ls 2f
	add w13, w13, #39
2:	strb w13, [x11], #1
	lsl w10, w10, #4
	subs w12, w12, #1
	b.ne 1b
	strb wzr, [x11]
	add x0, sp, #32
	mov x1, #0
	mov x2, #0
	mov x16, #5		// open
	svc #0x80
	ldp x2, x16, [sp, #16]
	ldp x0, x1, [sp], #64
	stp d9, d8, [sp, #-48]!	// the replaced instruction
	b . + (RETURN - (CAVE + 100))
	.balign 8
3:	.ascii "/sweetbr"
"""
CODE = bytes.fromhex('e007bca9e24301a909030058e91300f90a00261eeba300910c0180524d7d1c53adc10011bfe5007149000054ad9d00116d1500384a6d1c538c05007101ffff547f010039e0830091010080d2020080d2b00080d2011000d4e24341a9e007c4a8e923bd6d441e14152f73776565746272')


def assemble():
    import os, subprocess, tempfile
    source = ASSEMBLY.replace('RETURN', hex(FUNCTION + 4)).replace('CAVE', hex(CAVE))
    with tempfile.TemporaryDirectory() as t:
        open(t + '/a.s', 'w').write(source)
        subprocess.run(['aarch64-linux-gnu-as', t + '/a.s', '-o', t + '/a.o'], check=True)
        subprocess.run(['aarch64-linux-gnu-objcopy', '-O', 'binary', '-j', '.text', t + '/a.o', t + '/a.bin'], check=True)
        return open(t + '/a.bin', 'rb').read()


if __name__ == '__main__':
    code = assemble()
    print(len(code), code.hex())
    print('matches CODE' if code == CODE else 'DIFFERS from CODE')
