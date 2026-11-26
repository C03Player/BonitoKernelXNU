#!/usr/bin/env python3
"""Follow the phone's kernel log live into a file (through `usbbridge.py serve 2323:23`): what was printed survives a hang. klog.py OUT [SECONDS]"""
import socket, sys, time
s = socket.create_connection(('127.0.0.1', 2323), timeout=10)
time.sleep(1.5)
s.sendall(b'cat /dev/kmsg\n')
end = time.time() + float(sys.argv[2] if len(sys.argv) > 2 else 120)
s.settimeout(1)
with open(sys.argv[1], 'wb') as f:
    while time.time() < end:
        try:
            d = s.recv(65536)
        except socket.timeout:
            continue
        except OSError:
            break
        if not d:
            break
        f.write(d.replace(b'\r', b''))
        f.flush()
