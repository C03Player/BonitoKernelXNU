#!/usr/bin/env python3
"""Run a shell command on the booted Linux test image through `usbbridge.py serve 2323:23` (telnet, no password, USB link only).

  psh.py 'command'      prints the output; exit status = the command's
"""
import re, socket, sys, time

cmd = ' '.join(sys.argv[1:])
s = socket.create_connection(('127.0.0.1', 2323), timeout=10)
s.settimeout(float(__import__('os').environ.get('PSH_TIMEOUT', '60')))
buf = b''


def until(pat):
    global buf
    while True:
        m = re.search(pat, buf)
        if m:
            head, buf = buf[:m.start()], buf[m.end():]
            return head, m
        d = s.recv(65536)
        if not d:
            sys.exit('psh: connection closed')
        buf += d


until(rb'# ')
# the markers are split so the terminal's echo of the typed line does not match them
s.sendall(b"stty -echo 2>/dev/null; echo @@B''EGIN@@\n")
until(rb'@@BEGIN@@\r*\n')
s.sendall(cmd.encode() + b"\necho @@E''ND@@$?@@\n")
out, m = until(rb'@@END@@(\d+)@@')
out = re.sub(rb'\x1b\[[0-9;]*[A-Za-z]', b'', out).replace(b'\r', b'')
out = re.sub(rb'(?m)^(/[^#\n]* # )+', b'', out)
sys.stdout.buffer.write(out)
sys.exit(int(m.group(1)))
