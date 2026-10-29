#!/usr/bin/env python3
"""Exercise ZDS-style internal flash erase polling and RAM-based programming."""
import os
from pathlib import Path
import tempfile
from ez80_testlib import VM


class Code:
    def __init__(self): self.data = bytearray()
    def out(self, port, value): self.data.extend((0x3e, value, 0xed, 0x39, port))
    def write(self, address, value):
        self.data.extend((0x3e, value, 0x32, *address.to_bytes(3, 'little')))
    def sample(self, port, index):
        self.data.extend((0xed, 0x38, port, 0x32, *(0xffe100 + index).to_bytes(3, 'little')))
    def read(self, address, index):
        self.data.extend((0x3a, *address.to_bytes(3, 'little'), 0x32,
                          *(0xffe100 + index).to_bytes(3, 'little')))


with tempfile.TemporaryDirectory(prefix='f91-internal-flash-') as td:
    os.chdir(td)
    code = Code()
    # Reset protection rejects writes and erase.
    code.write(0x100, 0)
    code.sample(0xfb, 0)
    code.out(0xfc, 0); code.out(0xff, 2); code.sample(0xfb, 1)
    # ZDS unlocks protection, then runs its erase loader from internal RAM.
    code.out(0xf5, 0xb6); code.out(0xf5, 0x49); code.out(0xfa, 0)
    code.out(0xff, 2)
    # Exact ZDS wait sequence: in0 a,(FB); and 20; cp 20; jr nz,wait.
    code.data.extend(bytes.fromhex('ed38fbe620fe2020f7'))
    code.read(0x100, 2)
    code.write(0x100, 0x5a); code.write(0x100, 0x0f); code.read(0x100, 3)
    code.out(0xfc, 1); code.out(0xfd, 0); code.out(0xfe, 0)
    code.out(0xf6, 0x12); code.out(0xfe, 0); code.sample(0xf6, 4)
    code.out(0xff, 2); code.sample(0xfb, 5); code.read(0x800, 6)
    code.read(0x100, 7)  # Page erase must not affect its neighbour.
    code.out(0xfc, 0x80); code.out(0xfd, 0); code.out(0xfe, 0)
    code.out(0xf6, 0x34)
    code.out(0xfc, 0); code.out(0xff, 1); code.sample(0xfb, 8)
    code.read(0x100, 9)
    code.out(0xfc, 0x80); code.out(0xfe, 0); code.sample(0xf6, 10)
    code.out(0xff, 1); code.sample(0xfb, 11)
    code.out(0xfe, 0); code.sample(0xf6, 12)
    code.sample(0xff, 13)
    code.data.append(0x76)
    boot = Code(); boot.data.extend(bytes.fromhex('5bc3050000'))
    for offset, value in enumerate(code.data): boot.write(0xffe200 + offset, value)
    boot.data.extend(bytes.fromhex('c300e2ff'))
    bios = Path(td) / 'loader.bin'; bios.write_bytes(boot.data)
    vm = VM(bios, extra=('-nic', 'none'))
    try:
        vm.cmd('cont'); vm.halted(); vm.cmd('stop')
        sample = Path(td) / 'result.bin'
        vm.cmd('pmemsave', {'val': 0xffe100, 'size': 14, 'filename': str(sample)})
        expected = bytes([8, 2, 255, 10, 0x12, 0x20, 255, 10,
                          0x20, 255, 0x34, 0x20, 255, 0])
        assert sample.read_bytes() == expected, (sample.read_bytes().hex(), expected.hex())
    finally:
        vm.close()
    assert Path('ez80f91_0.0').read_bytes() == b'\xff' * (256 * 1024)
print('PASS: ZDS erase polling, memory/I/O programming, protection, page/mass erase, info selection, persistence')
