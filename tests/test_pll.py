#!/usr/bin/env python3
"""F91 PLL registers, clock propagation and arbitration against Timer0."""
from pathlib import Path
import re
import tempfile
from ez80_testlib import VM

class ROM:
    def __init__(self):
        self.b = bytearray([0x5b, 0xc3, 5, 0, 0])
        self.labels = {}; self.fixups = []
    def emit(self, *data): self.b.extend(data)
    def ld(self, op, value): self.emit(op, *value.to_bytes(3, 'little'))
    def out(self, port, value): self.emit(0x3e, value, 0xed, 0x39, port)
    def sample(self, port, address):
        self.emit(0xed, 0x38, port); self.ld(0x32, address)
    def wait(self, count=50000):
        self.ld(0x01, count)
        self.emit(0x0b, 0x78, 0xb1, 0x20, 0xfb)
    def pointer(self, address, label):
        self.emit(0x21); self.fixups.append((len(self.b), label)); self.emit(0, 0, 0)
        self.ld(0x22, address)
    def finish(self):
        for offset, label in self.fixups:
            self.b[offset:offset+3] = self.labels[label].to_bytes(3, 'little')
        return self.b

def regs(vm):
    return {k: int(v, 16) for k, v in re.findall(r'([A-Z0-9]+)=([0-9a-f]+)', vm.hmp('info registers'))}

def run(root, name, rom, expected=None, count_check=None, uart=None, frequency=10000000):
    image = root / (name + '.bin'); image.write_bytes(rom.finish())
    output = root / (name + '.uart')
    vm = VM(image, 'file:' + str(output) if uart is not None else 'none',
            extra=('-icount', 'shift=0'),
            machine='ez80f91-minimal,osc-frequency=' + str(frequency))
    try:
        for iteration in range(2):
            vm.cmd('cont'); vm.halted(); vm.cmd('stop')
            state = regs(vm)
            assert state['PC'] == rom.end, (name, state)
            saved = root / 'sample.bin'
            vm.cmd('pmemsave', {'val': 0xffe100, 'size': 64, 'filename': str(saved)})
            data = saved.read_bytes()
            if expected is not None:
                assert data[:len(expected)] == expected, (name, data.hex(), expected.hex())
            if count_check:
                count_check(data)
            if uart is not None:
                assert output.read_bytes() == uart * (iteration + 1), (name, output.read_bytes())
            if iteration == 0: vm.cmd('system_reset')
    finally:
        vm.close()
    print('PASS:', name, '(including reset)')

with tempfile.TemporaryDirectory(prefix='f91-pll-') as td:
    root = Path(td)
    r = ROM()
    for n in range(4): r.sample(0x5c+n, 0xffe100+n)
    r.out(0x5e, 0xff); r.sample(0x5e, 0xffe104)  # reserved mux preserves oscillator
    r.out(0x5e, 1); r.sample(0x5e, 0xffe105)    # cannot choose unlocked PLL
    r.out(0x5c, 5); r.out(0x5d, 0); r.out(0x5e, 0x40); r.out(0x5f, 5)
    r.sample(0x5f, 0xffe106); r.wait()
    r.sample(0x5f, 0xffe107); r.sample(0x5f, 0xffe108)
    r.out(0x5e, 0x81); r.sample(0x5e, 0xffe109)  # pump frozen while enabled
    r.out(0x5f, 0); r.sample(0x5f, 0xffe10a)    # cannot disable selected PLL
    r.out(0x5e, 3); r.sample(0x5e, 0xffe10b)    # reserved mux preserves PLL
    r.out(0x5e, 0); r.out(0x5f, 2)
    r.sample(0x5f, 0xffe10c); r.sample(0x5f, 0xffe10d)
    r.emit(0x76); r.end = len(r.b)
    run(root, 'pll-registers-latch-events-write-protection', r,
        bytes([0,0,0,0,0xcc,0,5,0x35,0x25,0x41,0x21,0x41,0x0a,2]))

    # Reading the timer low byte latches high. All samples are from a running timer.
    r = ROM(); r.out(0x5c, 5); r.out(0x5d, 0); r.out(0x5f, 1); r.wait()
    # Writes to divider while enabled must have no effect (remain 10 MHz * 5).
    r.out(0x5c, 2); r.out(0x5d, 0)
    r.out(0x64, 60000 >> 8); r.out(0x63, 60000 & 255); r.out(0x60, 0x83)
    def timer_sample(slot):
        r.sample(0x63, 0xffe100+2*slot); r.sample(0x64, 0xffe101+2*slot)
    timer_sample(0); r.wait(); timer_sample(1)
    r.out(0x5e, 1); r.wait(); timer_sample(2)
    r.out(0x5e, 2); r.wait(); timer_sample(3)
    r.out(0x5e, 0); r.wait(); timer_sample(4)
    r.out(0x60, 0); r.emit(0x76); r.end = len(r.b)
    def frequency_check(data):
        c = [int.from_bytes(data[n:n+2], 'little') for n in range(0,10,2)]
        deltas = [a-b for a,b in zip(c,c[1:])]
        assert 495 <= deltas[0] <= 505, deltas
        assert 2495 <= deltas[1] <= 2505, deltas
        assert 1 <= deltas[2] <= 4, deltas
        assert 495 <= deltas[3] <= 505, deltas
    run(root, 'running-timer-oscillator-pll-rtc-clock-switch', r, count_check=frequency_check)

    # Low divider writes are staged until high is written. N=0 is clamped to 2.
    r = ROM(); r.out(0x5c, 0); r.out(0x5d, 0); r.out(0x5c, 5)
    r.out(0x5f, 1); r.wait(); r.out(0x5e, 1)
    r.out(0x64, 60000 >> 8); r.out(0x63, 60000 & 255); r.out(0x60, 0x83)
    timer_sample(0); r.wait(); timer_sample(1)
    r.out(0x5e, 0); r.out(0x5f, 0); r.out(0x5d, 0); r.out(0x5f, 1); r.wait()
    r.out(0x5e, 1); timer_sample(2); r.wait(); timer_sample(3)
    r.out(0x60, 0); r.emit(0x76); r.end = len(r.b)
    def latch_check(data):
        c = [int.from_bytes(data[n:n+2], 'little') for n in range(0,8,2)]
        assert 995 <= c[0]-c[1] <= 1005, c
        assert 2495 <= c[2]-c[3] <= 2505, c
    run(root, 'divider-high-commit-and-minimum-two', r, count_check=latch_check)

    r = ROM(); r.out(0x5c,5); r.out(0x5d,0); r.out(0x5f,1)
    r.wait(100); r.out(0x5f,0); r.wait(); r.sample(0x5f,0xffe100)
    r.emit(0x76); r.end = len(r.b)
    run(root, 'disable-cancels-pending-lock', r, expected=b'\0')

    r = ROM(); r.out(0x5c,5); r.out(0x5d,0); r.out(0x5f,1); r.wait()
    r.sample(0x5f,0xffe100); r.out(0x5e,1); r.sample(0x5e,0xffe101)
    r.emit(0x76); r.end = len(r.b)
    run(root, 'invalid-pll-input-does-not-lock-or-switch', r,
        expected=b'\1\0', frequency=50000000)

    for high, order in ((0, b'PT'), (0x20, b'TP')):
        r = ROM(); r.ld(0x31, 0xfffff0)
        r.pointer(0xffe24c, 'pll'); r.pointer(0xffe254, 'timer')
        r.ld(0x21, 0xffe2); r.emit(0xed,0xc7)
        r.out(0xa3, 0xff); r.out(0xa4, 0); r.out(0xa5, 3); r.out(0xc3, 3)
        r.out(0x10, high); r.out(0x5c,5); r.out(0x5d,0); r.out(0x5f,5)
        r.out(0x64,0); r.out(0x63,250); r.out(0x61,1); r.out(0x60,0x83)
        r.wait(); r.emit(0xfb,0x00,0xf3,0x76); r.end = len(r.b)
        r.labels['pll'] = len(r.b)
        r.sample(0x5f,0xffe100); r.out(0xc0,ord('P')); r.emit(0xfb,0xed,0x4d)
        r.labels['timer'] = len(r.b)
        r.emit(0xed,0x38,0x62); r.out(0xc0,ord('T')); r.emit(0xfb,0xed,0x4d)
        run(root, 'pll-timer-arbitration-' + order.decode(), r, expected=b'\x35', uart=order)
