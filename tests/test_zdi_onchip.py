#!/usr/bin/env python3
"""Run the remaining ZDI register commands against the actual emulated CPU/RAM."""
from pathlib import Path
import sys
import tempfile
from ez80_testlib import VM

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/zds'))
from rsp import RSP
from zdi import ZDI

with tempfile.TemporaryDirectory(prefix='f91-zdi-regs-') as temp:
    root = Path(temp)
    rom = root / 'halt.bin'
    rom.write_bytes(b'\x76')
    path = root / 'gdb.sock'
    vm = VM(rom, extra=('-nic', 'none', '-gdb', f'unix:{path},server=on,wait=off'))
    g = RSP(unix=str(path))
    z = ZDI(g)
    try:
        assert g.memory(0x1000000, 3) == bytes(z.read(i) for i in range(3))
        z.write(0x17, 0xff)
        assert z.read(0x17) == 0xc0
        z.write(0x17, 0)
        assert z.read(0x17) == 0
        for adl in (0, 1):
            r = g.registers()
            r[18], r[17], r[0] = adl, 0xff, 0xffe200
            g.set_registers(r)
            g.write_memory(0xffe200, b'\x12\x34')
            z.write(0x16, 0x0b)
            assert z.read(0x10) == 0x12 and g.registers()[0] == 0xffe201
            z.write(0x13, 0xa5)
            z.write(0x16, 0x8b)
            assert g.memory(0xffe201, 1) == b'\xa5' and g.registers()[0] == 0xffe202
            r = g.registers()
            r[0] = 0xffffff
            g.set_registers(r)
            g.write_memory(0xffffff, b'\x5a')
            z.write(0x16, 0x0b)
            assert z.read(0x10) == 0x5a
            assert g.registers()[0] == (0 if adl else 0xff0000)
    finally:
        g.socket.close()
        vm.close()
print('PASS: I/O/ZDI product IDs agree; BUS_CTL/STAT masks, direct PC memory read/write and 16/24-bit wrap')
