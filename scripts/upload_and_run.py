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
import os
import re
import time
import serial
import sys


def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def discover_local_dependencies(local_main_path):
    """Return local sibling modules imported by the main script."""
    base_dir = os.path.dirname(os.path.abspath(local_main_path))
    code = read_file(local_main_path)
    modules = set()

    # Handle lines like "import foo, bar" and "from foo import x".
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        m_import = re.match(r'^import\s+(.+)$', stripped)
        if m_import:
            for part in m_import.group(1).split(','):
                mod = part.strip().split(' as ')[0].strip()
                if mod:
                    modules.add(mod.split('.')[0])
            continue

        m_from = re.match(r'^from\s+([A-Za-z_][A-Za-z0-9_\.]*)\s+import\s+', stripped)
        if m_from:
            modules.add(m_from.group(1).split('.')[0])

    deps = []
    for module_name in sorted(modules):
        local_candidate = os.path.join(base_dir, module_name + '.py')
        if os.path.isfile(local_candidate):
            deps.append((local_candidate, module_name + '.py'))

    return deps


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


def enter_raw_repl(ser, timeout=5.0):
    """Try to enter MicroPython raw REPL reliably."""
    for _ in range(3):
        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        # Interrupt any running program, then request raw REPL.
        ser.write(b"\x03\x03")
        time.sleep(0.2)
        ser.write(b"\x01")

        out = wait_for(ser, 'raw REPL; CTRL-B to exit', timeout=timeout)
        if 'raw REPL' in out:
            return True

        time.sleep(0.2)

    return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', default='rfc2217://localhost:4000', help='pyserial URL')
    p.add_argument('--local', default='esp32/main.py', help='Local file to upload')
    p.add_argument('--remote', default='main.py', help='Remote filename on device')
    p.add_argument('--timeout', type=float, default=8.0)
    p.add_argument('--no-auto-deps', action='store_true', help='Do not auto-upload local imported modules')
    args = p.parse_args()

    files_to_upload = [(args.local, args.remote)]
    if not args.no_auto_deps:
        files_to_upload.extend(discover_local_dependencies(args.local))

    # Remove duplicates preserving order by remote filename.
    dedup = []
    seen_remote = set()
    for local_path, remote_name in files_to_upload:
        if remote_name in seen_remote:
            continue
        seen_remote.add(remote_name)
        dedup.append((local_path, remote_name))
    files_to_upload = dedup

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
    if not enter_raw_repl(ser, timeout=args.timeout):
        print('Warning: did not detect raw REPL prompt; continuing anyway')
    else:
        print('Raw REPL ready')

    # Prepare payload to write file(s) and reset
    payload = []
    print('Arquivos para upload:')
    for local_path, remote_name in files_to_upload:
        code = read_file(local_path)
        print(' - {} -> {}'.format(local_path, remote_name))
        payload.append("f = open('%s','w')\n" % remote_name)
        # Write in chunks to avoid huge repr issues
        for i in range(0, len(code), 128):
            chunk = code[i:i+128]
            payload.append("f.write(%r)\n" % chunk)
        payload.append('f.close()\n')

    payload.append('import machine\n')
    payload.append('machine.reset()\n')

    program = ''.join(payload)

    # Send the program and finish with Ctrl-D to execute
    print('Uploading {} bytes...'.format(len(program)))
    encoded = program.encode('utf-8')
    for i in range(0, len(encoded), 256):
        ser.write(encoded[i:i+256])
        time.sleep(0.01)
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
