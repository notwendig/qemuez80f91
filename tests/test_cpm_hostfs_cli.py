#!/usr/bin/env python3
"""Boot actual CP/M/BIOS and run DIR, USER, PIP, REN and ERA on native files."""
from pathlib import Path
import select
import shutil
import socket
import sys
import tempfile
import time
from ez80_testlib import VM

ROOT = Path(__file__).resolve().parents[1]
image = ROOT / 'build/cpm-hostfs/cpm.bin'
with tempfile.TemporaryDirectory(prefix='cpm-native-cli-') as temp:
    work = Path(temp)
    files = work / 'files'
    (files / 'A/1').mkdir(parents=True)
    (files / 'D').mkdir()
    ramdisk = ROOT / 'subprojects/FreeRTOS-eZ80f91/CPM/RAMDSK'
    shutil.copyfile(ramdisk / 'PIP.COM', files / 'A/pip.com')
    shutil.copyfile(ramdisk / 'SDIR.COM', files / 'A/1/sdir.com')
    (files / 'A/readme.txt').write_bytes(b'NATIVE UNIX FILES\r\n\x1a')
    # A real transient calls BIOS disk entries; those execute IN/OUT (18h..1fh).
    program = bytearray()
    def call(address):
        program.extend(b'\xcd' + address.to_bytes(2, 'little'))
    def print_char(char):
        program.extend(bytes([0x1e, char, 0x0e, 2])); call(5)
    for char in b'FDC': print_char(char)
    program.extend(b'\x0e\x01'); call(0xfa1b)  # SELDSK B
    program.extend(b'\x01\x00\x00'); call(0xfa1e)
    program.extend(b'\x0e\x1a'); call(0xfa21)
    program.extend(b'\x01\x00\x40'); call(0xfa24)
    call(0xfa27)                              # READ track 0 / sector 1
    program.extend(b'\xc6\x30\x5f\x0e\x02'); call(5)
    program.extend(b'\x3a\x00\x40\x5f\x0e\x02'); call(5)
    program.extend(b'\xc3\x00\x00')
    (files / 'A/fdctest.com').write_bytes(program)
    coherent = bytes(program).replace(b'\x0e\x1a\xcd\x21\xfa', b'\x0e\x14\xcd\x21\xfa')
    (files / 'A/fdccoh.com').write_bytes(coherent)
    # Write back one byte through BIOS WRITE, then read it through FCB services.
    writer = coherent[:-3] + b'\x3eR\x32\x00\x40\xcd\x2a\xfa\xc3\x00\x00'
    (files / 'A/fdcput.com').write_bytes(writer)

    raw = bytearray(b'\xe5' * 256256)
    raw[25 * 128] = ord('Z')
    (files / 'B.img').write_bytes(raw)
    endpoint = work / 'console.sock'
    vm = VM(image, machine='ez80f91-freertos,ram-boot=on,cs3=none', loader='-kernel', extra=(
        '-nic', 'none', '-global', f'ez80f91-hostfs.root={files}',
        '-global', f'ez80f91-memory.dev-dir={files}', '-global', 'ez80f91-memory.wd2797a=24',
        '-chardev', f'socket,id=host,path={endpoint},server=on,wait=off',
        '-global', 'ez80f91-hostfs.chardev=host'))
    console = socket.socket(socket.AF_UNIX)
    console.connect(str(endpoint))
    console.setblocking(False)
    transcript = bytearray()
    def until(marker, timeout=10):
        text = bytearray()
        deadline = time.monotonic() + timeout
        while not text.endswith(marker):
            assert time.monotonic() < deadline, (marker, bytes(text), vm.hmp('info registers'))
            if select.select([console], [], [], .05)[0]:
                data = console.recv(65536)
                assert data, bytes(text)
                text += data
                transcript.extend(data)
        return bytes(text)
    def command(text, prompt=b'a>'):
        console.sendall(text.encode() + b'\r')
        return until(prompt)
    try:
        vm.cmd('cont')
        until(b'a>')
        listing = command('DIR')
        assert b'PIP' in listing and b'README' in listing and b'SDIR' not in listing, listing
        assert b'NATIVE UNIX FILES' in command('TYPE README.TXT')
        assert b'FDC0Z' in command('FDCTEST')
        command('PIP COPY.TXT=README.TXT')
        assert (files / 'A/copy.txt').read_bytes().startswith(b'NATIVE UNIX FILES\r\n\x1a')
        command('PIP D:CROSS.TXT=README.TXT')
        assert (files / 'D/cross.txt').read_bytes().startswith(b'NATIVE UNIX FILES\r\n\x1a')
        command('PIP B:IMAGE.TXT=README.TXT')
        assert b'FDC0N' in command('FDCCOH')
        command('B:', prompt=b'b>')
        assert b'NATIVE UNIX FILES' in command('TYPE IMAGE.TXT', prompt=b'b>')
        command('A:')
        assert b'FDC0N' in command('FDCPUT')
        command('PIP D:BACK.TXT=B:IMAGE.TXT')
        assert (files / 'D/back.txt').read_bytes().startswith(b'RATIVE UNIX FILES')
        command('D:', prompt=b'd>')
        assert b'NATIVE UNIX FILES' in command('TYPE CROSS.TXT', prompt=b'd>')
        command('A:')
        command('REN NEW.TXT=COPY.TXT')
        assert (files / 'A/new.txt').exists() and not (files / 'A/copy.txt').exists()
        command('ERA NEW.TXT')
        assert not (files / 'A/new.txt').exists()
        command('USER 1')
        listing = command('DIR')
        assert b'SDIR' in listing and b'PIP' not in listing, listing
        result = command('SDIR')
        assert b'SDIR' in result.upper() and b'File Not Found' not in result, result
        command('USER 0')
        # Host changes are visible on the very next BDOS directory scan.
        (files / 'A/live.txt').write_bytes(b'LIVE\x1a')
        assert b'LIVE' in command('DIR')
        console.sendall(b'\x03')
        until(b'a>')
        assert b'PIP' in command('DIR')
        (ROOT / 'build/cpm-hostfs/console-test.log').write_bytes(transcript)
        print('PASS: actual BIOS/BDOS CP/M 2.2, direct IN/OUT console, DIR/TYPE, PIP across image/directory drives, coherent FDC/FCB reads and writes, rename/delete, USER 1 SDIR and warm boot')
    finally:
        console.close()
        vm.close()
