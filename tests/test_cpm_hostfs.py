#!/usr/bin/env python3
"""Native CP/M FCB operations, user directories and low-byte I/O decoding."""
from pathlib import Path
import select
import socket
import sys
import subprocess
import hashlib
import tempfile
import time
from ez80_testlib import VM

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/zds'))
from rsp import RSP

with tempfile.TemporaryDirectory(prefix='cpm-hostfs-') as temp:
    work = Path(temp)
    root = work / 'files'
    (root / 'A/1').mkdir(parents=True)
    (root / 'D').mkdir()
    # Mix directory drives with both supported image geometries and bare files.
    for mount, fmt in [('B.img', 'ibm-3740-data'), ('I.img', '4mb-hd'), ('C', '4mb-hd')]:
        (root / mount).write_bytes(b'\xe5' * (4194304 if fmt == '4mb-hd' else 256256))
        subprocess.run(['mkfs.cpm', '-f', fmt, str(root / mount)],
                       cwd=ROOT / 'images/cpm', check=True)
        subprocess.run(['cpmcp', '-T', 'logical', '-f', fmt, str(root / mount),
                        str(ROOT / 'examples/camelf91/f24all.f24'), '0:F24ALL.F24'],
                       cwd=ROOT / 'images/cpm', check=True)
    original = bytes(i & 255 for i in range(300))
    (root / 'A/pip.com').write_bytes(original)
    (root / 'A/1/sdir.com').write_bytes(b'USER ONE')
    (root / 'D/test.f24').write_text(': SQUARE DUP * ;\n12 SQUARE .\n')
    (root / 'A/readonly.txt').write_bytes(b'KEEP')
    (root / 'A/readonly.txt').chmod(0o444)
    outside = work / 'outside.com'
    outside.write_bytes(b'PRIVATE')
    (root / 'A/link.com').symlink_to(outside)
    rom = work / 'halt.bin'
    rom.write_bytes(b'\x76')
    endpoint = work / 'console.sock'
    gdb = work / 'gdb.sock'
    vm = VM(rom, machine='ez80f91-freertos,ram-boot=on', loader='-kernel', extra=(
        '-nic', 'none', '-gdb', f'unix:{gdb},server=on,wait=off',
        '-global', f'ez80f91-hostfs.root={root}',
        '-chardev', f'socket,id=host,path={endpoint},server=on,wait=off',
        '-global', 'ez80f91-hostfs.chardev=host'))
    console = socket.socket(socket.AF_UNIX)
    console.connect(str(endpoint))
    console.settimeout(5)
    g = RSP(unix=str(gdb))
    def out(port, value):
        # Exactly the full address driven by OUT (n),A, without truncating A.
        g.write_memory(0x1000000 | (value << 8) | port, bytes([value]))
    def inp(port, high=0xa9):
        return g.memory(0x1000000 | (high << 8) | port, 1)[0]
    def command(op, request=b''):
        out(0x8e, 0)
        for byte in request:
            out(0x8f, byte)
        out(0x8e, op)
        return inp(0x8e)
    def bdos(fn, de=0x2000):
        request = bytes([fn, de & 255, de >> 8, 0, 0, 0x80])
        assert command(1, request) == 0
        return inp(0x8f) | inp(0x8f) << 8
    def fcb(name, drive=1):
        stem, _, ext = name.upper().partition('.')
        value = bytearray(36)
        value[0] = drive
        value[1:12] = (stem.ljust(8) + ext.ljust(3)).encode()
        return value
    def select(name, drive=1):
        g.write_memory(0x2000, fcb(name, drive))
    try:
        for high in range(256):
            assert inp(0x8c, high) & 0x82 == 0x82, high
        assert bdos(13, 0) == 0 and bdos(26, 0x3000) == 0
        assert bdos(24, 0) == 1
        assert bdos(14, 0xa903) == 0 and bdos(24, 0) == 9
        assert bdos(14, 0) == 0
        select('PIP.COM')
        assert bdos(15) == 0
        readback = bytearray()
        for _ in range(3):
            assert bdos(20) == 0
            readback += g.memory(0x3000, 128)
        assert readback == original + b'\x1a' * 84
        assert bdos(20) == 1
        assert (root / 'A/pip.com').read_bytes() == original
        assert bdos(32, 1) == 1
        select('SDIR.COM')
        assert bdos(15) == 0 and bdos(20) == 0
        assert g.memory(0x3000, 8) == b'USER ONE'
        assert bdos(32, 0) == 0
        select('LINK.COM')
        assert bdos(15) == 255
        select('READONLY.TXT')
        assert bdos(21) == 255
        select('NEW.DAT', 4)
        assert bdos(22) == 0
        data = bytes((i * 17) & 255 for i in range(128))
        g.write_memory(0x3000, data)
        assert bdos(21) == 0 and bdos(16) == 0
        assert (root / 'D/new.dat').read_bytes() == data
        value = fcb('NEW.DAT', 4)
        value[33] = 3
        g.write_memory(0x2000, value)
        assert bdos(40) == 0
        assert (root / 'D/new.dat').read_bytes() == data + bytes(256) + data
        assert bdos(35) == 0 and g.memory(0x2021, 3) == b'\x04\0\0'
        value = fcb('NEW.DAT', 4)
        value[17:28] = b'RENAMED DAT'
        g.write_memory(0x2000, value)
        assert bdos(23) == 0
        assert not (root / 'D/new.dat').exists() and (root / 'D/renamed.dat').exists()
        select('????????.???', 4)
        assert bdos(17) == 0
        directory = g.memory(0x3000, 32)
        assert directory[1:12] in (b'RENAMED DAT', b'TEST    F24')
        assert bdos(18) == 0 and bdos(18) == 255
        select('RENAMED.DAT', 4)
        assert bdos(19) == 0 and not (root / 'D/renamed.dat').exists()
        # The same FCB protocol operates on real CP/M images; independently
        # inspect their bytes with cpmtools rather than reusing emulator logic.
        for letter, mount, fmt in [('B', 'B.img', 'ibm-3740-data'),
                                   ('I', 'I.img', '4mb-hd'), ('C', 'C', '4mb-hd')]:
            disk = ord(letter) - ord('A') + 1
            select('MIXED.DAT', disk)
            assert bdos(22) == 0, letter
            payload = hashlib.shake_256(b'CP/M extent and block mapping').digest(17024)
            for pos in range(0, len(payload), 128):
                g.write_memory(0x3000, payload[pos:pos + 128])
                assert bdos(21) == 0, (letter, pos)
            assert bdos(16) == 0
            extracted = work / (letter + '-mixed.dat')
            subprocess.run(['cpmcp', '-T', 'logical', '-f', fmt, str(root / mount),
                            '0:MIXED.DAT', str(extracted)], cwd=ROOT / 'images/cpm', check=True)
            assert extracted.read_bytes() == payload, letter
            select('MIXED.DAT', disk)
            assert bdos(15) == 0
            for pos in range(0, len(payload), 128):
                assert bdos(20) == 0
                assert g.memory(0x3000, 128) == payload[pos:pos + 128]
            assert bdos(20) == 1
            # Random zero fill, extent rollover and attributes on an image.
            value = fcb('MIXED.DAT', disk); value[33:36] = (150).to_bytes(3, 'little')
            g.write_memory(0x2000, value); g.write_memory(0x3000, bytes([77]) * 128)
            assert bdos(40) == 0 and bdos(35) == 0
            assert g.memory(0x2021, 3) == (151).to_bytes(3, 'little')
            # Capacity is checked before modifying the original directory/data.
            snapshot = (root / mount).read_bytes()
            value = fcb('MIXED.DAT', disk); value[33:36] = (40000).to_bytes(3, 'little')
            g.write_memory(0x2000, value)
            assert bdos(40) == 255
            assert (root / mount).read_bytes() == snapshot
            select('MIXED.DAT', disk); value = fcb('MIXED.DAT', disk)
            value[9] |= 128; g.write_memory(0x2000, value)
            assert bdos(30) == 0 and bdos(21) == 255 and bdos(19) == 255
            select('MIXED.DAT', disk); assert bdos(30) == 0
            value = fcb('MIXED.DAT', disk); value[17:28] = b'RENAMED DAT'
            g.write_memory(0x2000, value); assert bdos(23) == 0
            select('RENAMED.DAT', disk); assert bdos(15) == 0 and bdos(19) == 0
            assert bdos(32, 1) == 1
            select('USER1.DAT', disk); assert bdos(22) == 0
            assert bdos(32, 0) == 0
            select('USER1.DAT', disk); assert bdos(15) == 255
        assert command(7) == 0
        line = b': ANSWER 4242 ;\r'
        console.sendall(line)
        until = time.monotonic() + 5
        chars = bytearray()
        while len(chars) < len(line) and time.monotonic() < until:
            if inp(0x8c) & 1:
                chars.append(inp(0x8d))
            else:
                time.sleep(.01)
        assert chars == line, chars
        assert command(6, b'\x03\0ANSWER.F24') == 0
        assert (root / 'D/answer.f24').read_bytes() == b': ANSWER 4242 ;\n'
        assert command(6, b'\x01\0ANSWER.F24') == 0
        assert command(2, b'\x01\0ANSWER.F24') == 0
        assert command(3) == 0
        size = inp(0x8f)
        assert bytes(inp(0x8f) for _ in range(size)) == b': ANSWER 4242 ;'
        assert command(3) == 0 and inp(0x8f) == 0
        assert command(6, b'\x10\0BAD.F24') == 255
        assert command(6, b'\x03\x10BAD.F24') == 255
        assert not (root / 'D/bad.f24').exists()
        assert command(2, b'\x00\0LINK.COM') == 255
        assert command(2, b'\x03\0TEST.F24') == 0
        source = bytearray()
        while True:
            assert command(3) == 0
            size = inp(0x8f)
            if not size:
                break
            source.extend(inp(0x8f) for _ in range(size))
            source += b'\n'
        assert source == (root / 'D/test.f24').read_bytes()
        for char in b'PORT CONSOLE':
            out(0x8d, char)
        received = bytearray()
        while len(received) < 12:
            received += console.recv(12 - len(received))
        assert received == b'PORT CONSOLE'
        assert outside.read_bytes() == b'PRIVATE'
        print('PASS: directory/image drives, independent cpmtools verification across extents, capacity, users, random I/O, attributes, rename/delete, Forth source and 8-bit console ports')
    finally:
        console.close()
        vm.close()
    # A: image has two reserved boot tracks; data writes must preserve them.
    boot_root = work / 'boot-root'
    boot_root.mkdir()
    boot_image = boot_root / 'A.img'
    boot_image.write_bytes(b'\xe5' * 256256)
    subprocess.run(['mkfs.cpm', '-f', 'ibm-3740', str(boot_image)],
                   cwd=ROOT / 'images/cpm', check=True)
    boot_tracks = bytes((i * 13) & 255 for i in range(6656))
    with boot_image.open('r+b') as output:
        output.write(boot_tracks)
    gdb2 = work / 'gdb2.sock'
    vm = VM(rom, machine='ez80f91-freertos,ram-boot=on', loader='-kernel', extra=(
        '-nic', 'none', '-gdb', f'unix:{gdb2},server=on,wait=off',
        '-global', f'ez80f91-hostfs.root={boot_root}'))
    g = RSP(unix=str(gdb2))
    try:
        assert bdos(13, 0) == 0 and bdos(26, 0x3000) == 0
        select('BOOTSAFE.DAT')
        assert bdos(22) == 0
        g.write_memory(0x3000, bytes([91]) * 128)
        assert bdos(21) == 0 and bdos(16) == 0
        assert boot_image.read_bytes()[:6656] == boot_tracks
        extracted = work / 'bootsafe.dat'
        subprocess.run(['cpmcp', '-T', 'logical', '-f', 'ibm-3740', str(boot_image), '0:BOOTSAFE.DAT', str(extracted)],
                       cwd=ROOT / 'images/cpm', check=True)
        assert extracted.read_bytes() == bytes([91]) * 128
        dpb = bdos(31, 0)
        assert g.memory(dpb + 13, 2) == b'\x02\x00'
        print('PASS: A: IBM-3740 image skew, actual DPB and preserved boot tracks')
    finally:
        vm.close()
