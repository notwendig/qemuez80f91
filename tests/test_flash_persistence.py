#!/usr/bin/env python3
"""Flash images survive QEMU restarts; missing/short images are erased."""
import json
from pathlib import Path
import zlib


def flash_payload(path):
    image = path.read_bytes()
    payload, trailer = image[:-4], image[-4:]
    assert int.from_bytes(trailer, 'little') == zlib.crc32(payload), path
    return payload

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
    assert flash_payload(root / 'ez80f91_0.0') == b'\xff' * (256 * 1024)
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
        data = flash_payload(root / f'ez80f91_{name}.0')
        assert len(data) == 1024 * 1024
        assert data[0] == 0x40 + index
        assert data[1:] == b'\xff' * (len(data) - 1)
    # Restart directly from persisted internal flash activates the same files.
    run(root, execute=True)
    assert flash_payload(root / 'ez80f91_0.0')[:len(code)] == code
    # Reject payload or trailer corruption without rewriting the damaged file.
    bad = root / 'ez80f91_0.0'
    original = bad.read_bytes()
    for offset in (10, len(original) - 1):
        broken = bytearray(original)
        broken[offset] ^= 1
        bad.write_bytes(broken)
        assert 'CRC32 mismatch' in run(root, check=False)
        assert bad.read_bytes() == broken
    bad.write_bytes(original)
    external = root / 'ez80f91_100000.0'
    broken = bytearray(external.read_bytes())
    broken[0] ^= 1
    external.write_bytes(broken)
    failure = subprocess.run([binary, '-M', 'ez80f91-minimal,cs0=flash',
        '-bios', str(bios), '-display', 'none', '-serial', 'none',
        '-monitor', 'none', '-nic', 'none'], cwd=root, capture_output=True,
        text=True, timeout=10)
    assert failure.returncode and 'CRC32 mismatch' in failure.stderr, failure.stderr
    assert external.read_bytes() == broken
    # Reject oversized input without overwriting it.
    bad = root / 'ez80f91_0.0'
    bad.write_bytes(b'\x55' * (256 * 1024 + 1))
    assert 'exceeds flash size' in run(root, check=False)
    assert bad.stat().st_size == 256 * 1024 + 1
print('PASS: internal startup, deferred external activation, actual CS bases, restart, FF fill')
