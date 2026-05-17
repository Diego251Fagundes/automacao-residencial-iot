#!/usr/bin/env python3
"""
Upload a local file to the Wokwi RFC2217 serial port and run it.

Usage:
  python scripts/upload_and_run.py --local esp32/main.py --remote main.py

This script connects to `rfc2217://localhost:4000` by default, toggles
control lines to avoid bootloader, enters raw REPL, writes the file and
issues a soft reset.
"""
import argparse
import time
import serial
import sys


def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def wait_for(ser, needle, timeout=5.0):
    end = time.time() + timeout
    buf = b''
    while time.time() < end:
        data = ser.read(ser.in_waiting or 1)
        if data:
            buf += data
            try:
                s = buf.decode('utf-8', errors='ignore')
            except Exception:
                s = ''
            if needle in s:
                return s
        else:
            time.sleep(0.01)
    return buf.decode('utf-8', errors='ignore')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', default='rfc2217://localhost:4000', help='pyserial URL')
    p.add_argument('--local', default='esp32/main.py', help='Local file to upload')
    p.add_argument('--remote', default='main.py', help='Remote filename on device')
    p.add_argument('--timeout', type=float, default=8.0)
    args = p.parse_args()

    code = read_file(args.local)

    print('Connecting to', args.port)
    ser = serial.serial_for_url(args.port, baudrate=115200, timeout=0.1)

    # Ensure RTS/DTR in a state that avoids bootloader on ESP32 in Wokwi
    try:
        ser.dtr = True
        ser.rts = True
    except Exception:
        pass

    # drain initial output
    time.sleep(0.2)
    ser.reset_input_buffer()

    # Enter raw REPL
    print('Requesting raw REPL (Ctrl-A)')
    ser.write(b"\x01")
    out = wait_for(ser, 'raw REPL; CTRL-B to exit', timeout=args.timeout)
    if 'raw REPL' not in out:
        print('Warning: did not detect raw REPL prompt; continuing anyway')
    else:
        print('Raw REPL ready')

    # Prepare payload to write file and reset
    payload = []
    payload.append("f = open('%s','w')\n" % args.remote)
    # write in chunks to avoid huge repr issues
    for i in range(0, len(code), 512):
        chunk = code[i:i+512]
        payload.append("f.write(%r)\n" % chunk)
    payload.append('f.close()\n')
    payload.append('import machine\n')
    payload.append('machine.reset()\n')

    program = ''.join(payload)

    # Send the program and finish with Ctrl-D to execute
    print('Uploading {} bytes...'.format(len(program)))
    ser.write(program.encode('utf-8'))
    time.sleep(0.05)
    ser.write(b"\x04")

    print('Waiting for device to reboot and run the script...')
    # read output for a while to show user
    t_end = time.time() + args.timeout
    output = ''
    while time.time() < t_end:
        data = ser.read(ser.in_waiting or 1)
        if data:
            try:
                s = data.decode('utf-8', errors='ignore')
            except Exception:
                s = ''
            output += s
            sys.stdout.write(s)
            sys.stdout.flush()
        else:
            time.sleep(0.05)

    ser.close()
    print('\nDone.')


if __name__ == '__main__':
    main()
