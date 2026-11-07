#!/usr/bin/env python3
"""Boot the ZDS FreeRTOS firmware and exercise its linked CAMEL24 task."""
from pathlib import Path
import re
import select
import socket
import sys
import tempfile
import time

from ez80_testlib import VM

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tools/zds'))
from ihex_to_bin import convert
from rsp import RSP

firmware = Path(sys.argv[2]).resolve()
map_text = firmware.with_suffix('.map').read_text(errors='replace')
tick_address = int(re.search(r'^_xTickCount\s+[DC]:([0-9A-F]+)', map_text, re.M)[1], 16)
with tempfile.TemporaryDirectory(prefix='freertos-camel-') as temp:
    work = Path(temp)
    root = work / 'drives'
    (root / 'A').mkdir(parents=True)
    (root / 'D').mkdir()
    # Timer1 and GPIO display words remain owned by the firmware LED driver.
    # Run the shared core checks without the standalone Kit peripheral commands.
    lines = (ROOT / 'examples/camelf91/f24all.f24').read_text().splitlines()
    lines = [line for line in lines if not any(word in line for word in
             ('BUTTON-INIT', 'BUTTONS', 'BUTTON?', 'SW1?', 'MATRIX-'))]
    (root / 'D/f24core.f24').write_text('\n'.join(lines) + '\n')
    binary = work / 'firmware.bin'
    convert(firmware, binary, 0x1000000)
    debug = firmware.name.lower().endswith('d.hex')
    image = binary.read_bytes()
    # ZDS emits a RAM-end marker as well as the ROM load image.
    binary.write_bytes(image[:0x40000])
    if not debug and any(b != 255 for b in image[0x40000:0x140000]):
        (work / 'ez80f91_040000.0').write_bytes(image[0x40000:0x140000])
    endpoint = work / 'camel.sock'
    gdb = work / 'gdb.sock'
    uart = work / 'uart.txt'
    debug = firmware.name.lower().endswith('d.hex')
    vm = VM(binary, serial='file:' + str(uart),
            machine='ez80f91-freertos', loader='-bios', cwd=work,
            extra=('-icount', 'shift=5,sleep=off', '-nic', 'none',
                   '-gdb', f'unix:{gdb},server=on,wait=off',
                   '-global', f'ez80f91-hostfs.root={root}',
                   '-chardev', f'socket,id=camel,path={endpoint},server=on,wait=off',
                   '-global', 'ez80f91-hostfs.chardev=camel'))
    console = socket.socket(socket.AF_UNIX)
    console.connect(str(endpoint))
    console.setblocking(False)
    debugger = RSP(unix=str(gdb))
    transcript = bytearray()
    pending = bytearray()
    def until(marker, timeout=30):
        deadline = time.monotonic() + timeout
        while marker not in pending:
            assert time.monotonic() < deadline, (bytes(pending[-600:]), uart.read_bytes()[-600:], vm.hmp('info registers'))
            if select.select([console], [], [], .05)[0]:
                data = console.recv(65536)
                assert data, 'CAMEL console disconnected'
                pending.extend(data)
                transcript.extend(data)
        end = pending.index(marker) + len(marker)
        result = bytes(pending[:end])
        del pending[:end]
        return result
    def command(line, timeout=30):
        console.sendall(line.encode() + b'\r')
        return until(b'\r\nOK ', timeout)
    def ticks():
        vm.cmd('stop')
        try:
            return int.from_bytes(debugger.memory(tick_address, 3), 'little')
        finally:
            vm.cmd('cont')
    try:
        vm.cmd('cont')
        greeting = until(b'CEST\r\n')
        assert b'Camel FORTH' in greeting and b'FreeRTOS' in greeting, greeting
        assert b'579' in command('DECIMAL 123 456 + .')
        assert b'B80000' in command('HEX HERE U. DECIMAL')
        command(': RAM-CHECK 31415 ;')
        result = command("HEX ' RAM-CHECK U. DECIMAL")
        address = int(re.findall(rb'\b[0-9A-F]{6}\b', result)[-1], 16)
        assert 0xB80000 <= address < 0xB8E000, result
        assert b'31415' in command('RAM-CHECK .')
        builtin = re.search(r'^DUP\s+C:([0-9A-F]+)', map_text, re.M)
        assert builtin and int(builtin[1], 16) < 0x140000
        first = ticks()
        deadline = time.monotonic() + 5
        while ticks() == first:
            assert time.monotonic() < deadline, 'Waiting for KEY stalled the scheduler'
            time.sleep(.02)
        for line in (ROOT / 'examples/camelf91/file-words.f24').read_text().splitlines():
            if line.strip():
                result = command(line)
                assert b'?' not in result, result
        command('HOLDP @ HP !')
        result = command('3 S" F24CORE.F24" LOAD', 120)
        assert b'TESTS 194 FAILURES 0' in result, result[-600:]
        assert b'FILE ERROR' not in result and b'ASSERT' not in uart.read_bytes()
        command(': RTOS-ANSWER 4242 ;')
        command('3 S" RTOS.F24" SAVE')
        assert b': RTOS-ANSWER 4242 ;\n' in (root / 'D/rtos.f24').read_bytes()
        assert b'4242' in command('RTOS-ANSWER .')
        assert b'UT ' in uart.read_bytes(), uart.read_bytes()[-600:]
        first = ticks()
        console.sendall(b'bye\r')
        deadline = time.monotonic() + 5
        while ticks() == first:
            assert time.monotonic() < deadline, 'BYE stopped the scheduler'
            time.sleep(.02)
        (ROOT / 'build/freertos-camel').mkdir(exist_ok=True)
        (ROOT / 'build/freertos-camel' / ('debug.log' if debug else 'release.log')).write_bytes(transcript)
        print('PASS: linked FreeRTOS CAMEL24 task, private stack/dictionary, scheduler while waiting, 194 core Forth checks, numeric SAVE and BYE')
    finally:
        console.close()
        vm.close()
