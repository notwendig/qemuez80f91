#!/usr/bin/env python3
"""Emit the small raw eZ80 ROM documented in hello_uart0.asm (no SDK required)."""
from pathlib import Path
import sys

rom = bytearray()
labels = {}
fixups = []

def emit(*data):
    rom.extend(data)

def label(name):
    labels[name] = len(rom)

def absolute(opcode, name, prefix=()):
    emit(*prefix, opcode)
    fixups.append((len(rom), name, 3))
    emit(0, 0, 0)

def relative(opcode, name):
    emit(opcode)
    fixups.append((len(rom), name, 1))
    emit(0)

def out(port, value):
    emit(0x3e, value, 0xed, 0x39, port)

absolute(0xc3, 'start', (0x5b,))  # JP.LIL start
label('start')
emit(0xf3, 0x31, 0xf0, 0xff, 0xff)  # DI; LD SP,FFFFF0h
out(0xa3, 0xff)
out(0xa4, 0)
out(0xa5, 3)
out(0xc3, 0x83)
out(0xc0, 2)
out(0xc1, 0)
out(0xc3, 3)
out(0xc1, 0)
out(0xc2, 0)
absolute(0x21, 'message')
absolute(0xcd, 'puts')
emit(0x76)
label('puts')
emit(0x7e, 0xb7)  # LD A,(HL); OR A
relative(0x28, 'done')
emit(0xe5)  # PUSH HL
absolute(0xcd, 'putc')
emit(0xe1, 0x23)  # POP HL; INC HL
relative(0x18, 'puts')
label('done')
emit(0xc9)
label('putc')
emit(0xf5)
label('wait')
emit(0xed, 0x38, 0xc5, 0xe6, 0x20)
relative(0x28, 'wait')
emit(0xf1, 0xed, 0x39, 0xc0, 0xc9)
label('message')
rom.extend(b'Hello eZ80F91\r\n\0')
for offset, name, size in fixups:
    value = labels[name]
    if size == 1:
        value -= offset + 1
        assert -128 <= value <= 127
        value &= 0xff
    rom[offset:offset+size] = value.to_bytes(size, 'little')
output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('hello_uart0.bin')
output.write_bytes(rom)
print(f'{output}: {len(rom)} bytes')
