#!/usr/bin/env python3
"""Flash images survive QEMU restarts; missing/short images are erased."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

binary = str(Path(sys.argv[1]).resolve())


def run(root, extra=(), check=True, execute=False):
    p = subprocess.Popen(
        [binary, '-M', 'ez80f91-minimal,cs0=flash,cs1=flash,cs2=flash,cs3=flash',
         '-S', '-display', 'none', '-serial', 'none', '-monitor', 'none',
         '-nic', 'none', '-qmp', 'stdio', *extra], cwd=root,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True)
    greeting = p.stdout.readline()
    if check:
        assert 'QMP' in greeting, p.stderr.read()
        for cmd in (('qmp_capabilities', 'cont') if execute else ('qmp_capabilities', 'quit')):
            p.stdin.write(json.dumps({'execute': cmd}) + '\n')
            p.stdin.flush()
            while True:
                response = json.loads(p.stdout.readline())
                if 'event' not in response:
                    assert 'return' in response, response
                    break
    if check and execute:
        import time
        time.sleep(.1)
        p.stdin.write('{"execute":"quit"}\n')
        p.stdin.flush()
        p.communicate(timeout=10)
        assert p.returncode == 0
        return ''
    p.wait(timeout=10)
    errors = p.stderr.read()
    assert (p.returncode == 0) == check, errors
    return errors


with tempfile.TemporaryDirectory(prefix='ez80-flash-persistence-') as td:
    root = Path(td)
    run(root)
    assert sorted(p.name for p in root.iterdir()) == ['ez80f91_0.0']
    assert (root / 'ez80f91_0.0').read_bytes() == b'\xff' * (256 * 1024)
    names = ['100000', '400000', '800000', 'C00000']
    # Guest explicitly sets lower/upper bounds, then activates each CS.
    code = bytearray([0x5b, 0xc3, 5, 0, 0])
    for cs, base in enumerate((0x10, 0x40, 0x80, 0xc0)):
        for port, value in ((0xa8 + cs * 3, base),
                            (0xa9 + cs * 3, base + 15),
                            (0xaa + cs * 3, 8)):
            code.extend((0x3e, value, 0xed, 0x39, port))
    code.append(0x76)
    bios = root / 'seed.bin'
    bios.write_bytes(code)
    for index, name in enumerate(names):
        (root / f'ez80f91_{name}.0').write_bytes(bytes([0x40 + index]))
    # Startup alone leaves external files untouched.
    run(root)
    for index, name in enumerate(names):
        assert (root / f'ez80f91_{name}.0').read_bytes() == bytes([0x40 + index])
    run(root, ['-bios', str(bios)], execute=True)
    for index, name in enumerate(names):
        data = (root / f'ez80f91_{name}.0').read_bytes()
        assert len(data) == 1024 * 1024
        assert data[0] == 0x40 + index
        assert data[1:] == b'\xff' * (len(data) - 1)
    # Restart directly from persisted internal flash activates the same files.
    run(root, execute=True)
    assert (root / 'ez80f91_0.0').read_bytes()[:len(code)] == code
    # Reject oversized input without overwriting it.
    bad = root / 'ez80f91_0.0'
    bad.write_bytes(b'\x55' * (256 * 1024 + 1))
    assert 'exceeds flash size' in run(root, check=False)
    assert bad.stat().st_size == 256 * 1024 + 1
print('PASS: internal startup, deferred external activation, actual CS bases, restart, FF fill')
