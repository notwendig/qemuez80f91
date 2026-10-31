#!/usr/bin/env python3
"""Hostname CLI forwarding/validation and guest board configuration, including reset."""
from pathlib import Path
import os
import socket
import subprocess
import sys
import tempfile
from unittest.mock import patch
from ez80_testlib import VM, binary

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import start

for port, supplied, expected in ((4040, None, 'ez804040'),
                                  (4041, None, 'ez804041'),
                                  (4040, 'Labor-4040', 'Labor-4040')):
    argv = ['start.py', '--session', str(port), binary]
    if supplied is not None:
        argv += ['--hostname', supplied]
    with patch.object(sys, 'argv', argv), patch.object(start, 'check_qemu'), \
            patch.object(start, 'terminal_session', return_value=0) as session:
        assert start.main() == 0
        assert session.call_args.args[-1] == expected, session.call_args
for name in ('', '-bad', 'bad-', 'bad.name', 'bad,name', 'ä', 'a' * 64):
    with patch.object(sys, 'argv', ['start.py', '--session', '4040', binary,
                                   '--hostname', name]), patch('sys.stderr'):
        try:
            start.main()
        except SystemExit as error:
            assert error.code == 2
        else:
            raise AssertionError(name)

with tempfile.TemporaryDirectory(prefix='f91-hostname-') as temp:
    root = Path(temp)
    shim = root / 'python3'
    shim.write_text('#!/bin/sh\nprintf "<%s>\\n" "$@"\n')
    shim.chmod(0o755)
    result = subprocess.run([str(ROOT / 'start.sh'), '--hostname', 'Labor-4040',
                             '--run', 'dbgport', '4041'], capture_output=True,
                            text=True, env={**os.environ, 'QEMU_EZ80': binary,
                                            'PATH': str(root) + ':' + os.environ['PATH']}, check=True)
    assert '<4041>' in result.stdout and '<--hostname>\n<Labor-4040>' in result.stdout, result

    # Exercise actual CPU IN/OUT instructions; the descriptor is read-only.
    rom = bytearray([0x5b, 0xc3, 5, 0, 0])
    rom += bytes([0x01, 0x0c, 0xff, 0, 0x3e, ord('!'), 0xed, 0x79])
    for offset in range(68):
        rom += b'\x01' + (0xff08 + offset).to_bytes(3, 'little') + b'\xed\x78'
        rom += b'\x32' + (0xffe100 + offset).to_bytes(3, 'little')
    rom += b'\x76'
    firmware = root / 'probe.bin'
    firmware.write_bytes(rom)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    cases = [((), 'ez800', 'ez80f91-minimal'),
             (('--dbgport=' + str(port),), f'ez80{port}', 'ez80f91-minimal'),
             ((), 'Labor-4040', 'ez80f91-minimal,hostname=Labor-4040'),
             (('-global', 'ez80f91-memory.hostname=' + 'a' * 63), 'a' * 63, 'ez80f91-minimal')]
    for extra, expected, machine in cases:
        vm = VM(firmware, extra=('-nic', 'none', *extra), machine=machine)
        try:
            for attempt in range(2):
                if attempt:
                    vm.cmd('system_reset')
                vm.cmd('cont')
                vm.halted()
                vm.cmd('stop')
                samples = root / 'samples.bin'
                vm.cmd('pmemsave', dict(val=0xffe100, size=68, filename=str(samples)))
                assert samples.read_bytes() == b'HOST' + expected.encode().ljust(64, b'\0')
        finally:
            vm.close()
    for name in ('', '-bad', 'bad-', 'bad.name', 'ä', 'a' * 64):
        result = subprocess.run([binary, '-M', 'ez80f91-minimal', '-display', 'none',
                                 '-global', 'ez80f91-memory.hostname=' + name],
                                cwd=root, capture_output=True, text=True, timeout=10)
        assert result.returncode and 'hostname' in result.stderr, result
print('PASS: default/custom hostname, CLI validation/forwarding, guest I/O and reset')
