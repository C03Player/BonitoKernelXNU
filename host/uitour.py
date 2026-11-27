#!/usr/bin/env python3
"""Walk through the hosted iOS by injected touches and take a screenshot after every step, to find visual faults.

  uitour.py OUTDIR [STEPS_FILE]      the phone is booted, `xnu-run` has been started and the bridge is up (host/psh.py)

A steps file has one step per line: "NAME SECONDS COMMAND..." where COMMAND is a host/touch.py command (or "-" for none) and SECONDS
the wait before the screenshot. Without a file the built-in tour runs. Screenshots hold Apple artwork: keep them out of Git.
"""
import os, subprocess, sys, time

TOUR = """
lock        2  key power
home        6  swipe 540 2150 540 500 20
page-left   3  swipe 950 1100 120 1100 14
page-right  3  swipe 120 1100 950 1100 14
control     4  control
control-off 3  swipe 540 1900 540 300 12
notif       4  notifications
notif-off   3  home
settings    8  tap 140 524
set-scroll  4  swipe 540 1600 540 500 16
set-top     4  swipe 540 500 540 1900 16
wifi        8  tap 540 760
back        4  tap 90 150
home2       4  home
safari      9  tap 540 2018
home3       4  home
switcher    5  switcher
home4       4  home
"""

here = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1]
os.makedirs(out, exist_ok=True)
text = open(sys.argv[2]).read() if len(sys.argv) > 2 else TOUR
for i, line in enumerate(l for l in text.split('\n') if l.strip() and not l.startswith('#')):
    name, wait, *cmd = line.split()
    if cmd and cmd[0] != '-':
        subprocess.run([sys.executable, here + '/touch.py'] + cmd, stdout=subprocess.DEVNULL, timeout=90)
    time.sleep(float(wait))
    shot = f'{out}/{i:02d}-{name}.png'
    r = subprocess.run([sys.executable, here + '/fbshot.py', shot], capture_output=True, text=True, timeout=90)
    print(name, 'ok' if r.returncode == 0 else r.stderr.strip()[-200:], flush=True)
