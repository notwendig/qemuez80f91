#!/usr/bin/env python3
"""Execute watchdog NMIs/RETN in all F91 memory modes and sleep-reset sources."""
from pathlib import Path
import re
import tempfile
import time
from ez80_testlib import VM


class Code:
    def __init__(self, long=True):
        self.b = bytearray()
        self.long = long

    def emit(self, *data): self.b.extend(data)
    def ld(self, op, value): self.emit(op, *value.to_bytes(3 if self.long else 2, 'little'))
    def out(self, port, value): self.emit(0x3e, value, 0xed, 0x39, port)


def registers(vm):
    return {name: int(value, 16) for name, value in
            re.findall(r'([A-Z0-9]+)=([0-9a-f]+)', vm.hmp('info registers'))}


def await_byte(vm, root, address, expected):
    target = root / 'result'
    end = time.monotonic() + 6
    while time.monotonic() < end:
        vm.cmd('stop')
        vm.cmd('pmemsave', {'val': address, 'size': 1, 'filename': str(target)})
        if target.read_bytes() == bytes([expected]):
            return
        vm.cmd('cont')
        time.sleep(.01)
    raise AssertionError((address, target.read_bytes(), registers(vm)))


with tempfile.TemporaryDirectory(prefix='f91-nmi-') as temp:
    root = Path(temp)
    for adl, madl in ((0, 0), (0, 1), (1, 0), (1, 1)):
        for iff in (0, 1):
            bank = 0 if not adl else 0xff
            result = (bank << 16) | 0xe100
            boot = Code()
            boot.emit(0x5b, 0xc3, 5, 0, 0, 0xf3)
            boot.ld(0x31, (bank << 16) | 0xfff0)
            if bank == 0:
                boot.out(0xb5, 0)
            if madl:
                boot.emit(0xed, 0x7d)
            if not adl:
                boot.emit(0x40, 0xc3, 0, 2)
            else:
                boot.ld(0xc3, 0x200)
            code = Code(bool(adl))
            if not adl:
                code.ld(0x31, 0xfff0)
            code.emit(0xfb if iff else 0xf3, 0)
            code.out(0x93, 0xcb)
            # Busy waiting keeps the post-interrupt program counter stable.
            loop = 0x200 + len(code.b)
            code.ld(0x3a, result)
            code.emit(0xfe, 0xdb)
            code.emit(0x20, (loop - (0x200 + len(code.b) + 2)) & 255)
            code.emit(0x3e, 0x42)
            code.ld(0x32, result + 2)
            done = 0x200 + len(code.b)
            code.ld(0xc3, done)
            handler = Code(bool(adl or madl))
            handler.emit(0xed, 0x38, 0x93)
            handler.ld(0x32, result)
            if madl:
                handler.ld(0x21, 0)
                handler.emit(0x39, 0x7e)
                handler.ld(0x32, result + 1)
            handler.out(0x94, 0xa5)
            handler.out(0x94, 0x5a)
            if madl:
                handler.emit(0x5b)
            handler.emit(0xed, 0x45)
            assert len(boot.b) < 0x66 and 0x66 + len(handler.b) < 0x200
            image = bytearray(0x200 + len(code.b))
            image[:len(boot.b)] = boot.b
            image[0x66:0x66 + len(handler.b)] = handler.b
            image[0x200:] = code.b
            rom = root / 'nmi.bin'
            rom.write_bytes(image)
            vm = VM(rom, extra=('-nic', 'none'))
            try:
                vm.cmd('cont')
                await_byte(vm, root, result + 2, 0x42)
                state = registers(vm)
                assert state['ADL'] == adl and state['IFF1'] == iff, state
                if madl:
                    path = root / 'frame'
                    vm.cmd('pmemsave', {'val': result + 1, 'size': 1, 'filename': str(path)})
                    assert path.read_bytes() == bytes([2 | adl])
            finally:
                vm.close()
            print(f'PASS: watchdog NMI + RETN, ADL={adl}, MADL={madl}, IEF1={iff}')

    for source in ('watchdog', 'rtc'):
        code = Code()
        code.emit(0x5b, 0xc3, 5, 0, 0, 0xf3)
        code.emit(0xed, 0x38, 0x93 if source == 'watchdog' else 0xed)
        code.ld(0x32, 0xffe100)
        code.emit(0xe6, 0x20 if source == 'watchdog' else 2, 0x20, 0)
        branch = len(code.b) - 1
        if source == 'watchdog':
            code.out(0x93, 0x87)  # RTC-derived watchdog keeps running in SLEEP.
        else:
            code.out(0xed, 1)
            for offset, value in enumerate((0, 0, 0, 1, 1, 1, 24, 20)):
                code.out(0xe0 + offset, value)
            code.out(0xe8, 1)
            code.out(0xec, 1)
            code.out(0xed, 0x40)
        # Configure a system-clock timer: SLEEP must freeze it.
        code.out(0x64, 255)
        code.out(0x63, 255)
        code.out(0x60, 7)
        code.emit(0xed, 0x76)
        code.ld(0xc3, len(code.b))
        success = len(code.b)
        code.b[branch] = success - branch - 1
        code.emit(0x3e, 0x42)
        code.ld(0x32, 0xffe101)
        done = len(code.b)
        code.ld(0xc3, done)
        rom = root / 'sleep.bin'
        rom.write_bytes(code.b)
        vm = VM(rom, extra=('-nic', 'none', '-rtc', 'clock=vm'))
        try:
            vm.cmd('cont')
            await_byte(vm, root, 0xffe101, 0x42)
            assert registers(vm)['SLEEP'] == 0
        finally:
            vm.close()
        print(f'PASS: {source} alarm recovers CPU from SLEEP through reset and records cause')
