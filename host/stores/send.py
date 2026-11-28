#!/usr/bin/env python3
"""send.py LOCAL REMOTE: copy a file to the phone over the USB cable and check it. Needs the bridge with port 9999:
`python3 bonito/tools/usbbridge.py serve 2323:23 9999:9999`."""
import hashlib, os, socket, subprocess, sys, threading, time

PSH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'psh.py')


def shell(command):
    return subprocess.run([sys.executable, PSH, command], capture_output=True, text=True, timeout=90).stdout


def attempt(data, remote):
    shell('killall nc 2>/dev/null; rm -f %s; setsid sh -c "nc -l -p 9999 > %s" >/dev/null 2>&1 </dev/null & sleep 2' % (remote, remote))
    link = socket.create_connection(('127.0.0.1', 9999), timeout=200)
    threading.Thread(target=lambda: link.sendall(data), daemon=True).start()
    for _ in range(60):
        time.sleep(2)
        if ' %d ' % len(data) in shell('echo SIZE $(stat -c %%s %s) .' % remote):
            break
    link.close()
    time.sleep(1)
    return hashlib.sha256(data).hexdigest() in shell('sha256sum %s' % remote)


def main():
    data = open(sys.argv[1], 'rb').read()
    for _ in range(3):
        if attempt(data, sys.argv[2]):
            print('sent', sys.argv[2], len(data))
            return
        time.sleep(10)
    sys.exit('%s: could not send it' % sys.argv[2])


main()
