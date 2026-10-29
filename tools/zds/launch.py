#!/usr/bin/env python3
"""Start QEMU and its ZDS II Ethernet Smart Cable endpoint together."""
import argparse
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu',default='/tmp/qemuez80f91-build-baseline/qemu-system-ez80')
    parser.add_argument('--bios',type=Path,default=ROOT/'examples/camelf91/camel.bin')
    parser.add_argument('--machine',choices=['ez80f91-minimal','ez80f91-freertos'],default='ez80f91-minimal')
    parser.add_argument('--port',type=int,default=4040)
    parser.add_argument('--gdb-port',type=int,default=1234)
    parser.add_argument('--serial',default='stdio',help='QEMU serial backend; default: stdio')
    parser.add_argument('--verbose',action='store_true')
    args = parser.parse_args()
    if not args.bios.is_file(): parser.error(f'BIOS not found: {args.bios}')
    command = [args.qemu,'-M',args.machine,'-bios',str(args.bios),'-S',
               '-gdb',f'tcp:127.0.0.1:{args.gdb_port}',
               '-display','none','-monitor','none','-serial',args.serial]
    children = []
    try:
        qemu = subprocess.Popen(command); children.append(qemu)
        # A short TCP readiness probe is safe: QEMU permits a new GDB session
        # after this probe disconnects. No guest instruction runs before -S.
        for _ in range(100):
            if qemu.poll() is not None: raise RuntimeError('QEMU startup failed')
            try:
                with socket.create_connection(('127.0.0.1',args.gdb_port),timeout=.1): pass
                break
            except OSError: time.sleep(.05)
        else: raise RuntimeError('QEMU GDB startup timed out')
        bridge_command = [sys.executable,str(ROOT/'tools/zds/ethernet.py'),
                          '--port',str(args.port),'--gdb-port',str(args.gdb_port),
                          '--listen','0.0.0.0','--scan-dev']
        if args.verbose: bridge_command.append('--verbose')
        bridge = subprocess.Popen(bridge_command); children.append(bridge)
        print(f'ZDS II: Ethernet Smart Cable → 127.0.0.1:{args.port}; CPU wartet auf Debugger.',flush=True)
        while qemu.poll() is None and bridge.poll() is None: time.sleep(.2)
        return (bridge.returncode or qemu.returncode or 0)
    except KeyboardInterrupt:
        return 0
    finally:
        for child in reversed(children):
            if child.poll() is None: child.terminate()
        for child in reversed(children):
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: child.kill(); child.wait()

if __name__ == '__main__': sys.exit(main())
