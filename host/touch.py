#!/usr/bin/env python3
"""Send touches to the hosted iOS (records appended to /tmp/xnuinput on the phone, as host/evrelay.c writes them), through psh.py.

  touch.py tap X Y | swipe X1 Y1 X2 Y2 [STEPS] | key power|volup|voldown     (panel pixels, 1080x2160)
  touch.py long X Y [MS]                 press and hold
  touch.py home | switcher | control | notifications      the system gestures (swipes from the screen's edges)
"""
import base64, os, struct, subprocess, sys

EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
rec = lambda t, c, v: struct.pack('<HHi', t, c, v)
syn = rec(EV_SYN, 0, 0)


def down(x, y):
    return rec(EV_ABS, 0x2f, 0) + rec(EV_ABS, 0x39, 1) + rec(EV_ABS, 0x35, x) + rec(EV_ABS, 0x36, y) + syn


def move(x, y):
    return rec(EV_ABS, 0x2f, 0) + rec(EV_ABS, 0x35, x) + rec(EV_ABS, 0x36, y) + syn


up = rec(EV_ABS, 0x2f, 0) + rec(EV_ABS, 0x39, -1) + syn
a = sys.argv[1:]
# the system gestures as plain swipes; "hold:N" keeps the finger down N frames at the end
hold = 0
if a[0] in ('home', 'switcher', 'control', 'notifications'):
    g = {'home': (540, 2155, 540, 1000, 10), 'switcher': (540, 2155, 540, 1300, 20),
         'control': (1000, 5, 1000, 900, 14), 'notifications': (300, 5, 300, 1400, 14)}[a[0]]
    hold = 40 if a[0] == 'switcher' else 0
    a = ['swipe'] + [str(v) for v in g]
frames = []		# record batches, sent with a short pause between them
if a[0] == 'tap':
    frames = [down(int(a[1]), int(a[2])), up]
elif a[0] == 'swipe':
    x1, y1, x2, y2 = map(int, a[1:5])
    n = int(a[5]) if len(a) > 5 else 12
    frames = [down(x1, y1)] + [move(x1 + (x2 - x1) * i // n, y1 + (y2 - y1) * i // n) for i in range(1, n + 1)]
    frames += [move(x2, y2)] * hold + [up]
elif a[0] == 'long':
    x, y = int(a[1]), int(a[2])
    frames = [down(x, y)] + [move(x, y)] * max(1, (int(a[3]) if len(a) > 3 else 900) // 20) + [up]
elif a[0] == 'key':
    k = {'power': 116, 'volup': 115, 'voldown': 114}[a[1]]
    frames = [rec(EV_KEY, k, 1) + syn, rec(EV_KEY, k, 0) + syn]
cmd = '; '.join("echo %s | base64 -d >> /tmp/xnuinput; usleep 16000" % base64.b64encode(f).decode() for f in frames)
here = os.path.dirname(os.path.abspath(__file__))
subprocess.run([sys.executable, here + '/psh.py', cmd], check=True, timeout=60)
