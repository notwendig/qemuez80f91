#!/usr/bin/env python3
"""Run unmodified vectors24.asm, install Timer0 ISR and verify the full wrapper."""
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import time
from ez80_testlib import VM

fixture = (Path(sys.argv[2]) if len(sys.argv) > 2 else
           Path(__file__).resolve().parents[1] / 'examples/timer0_vectors/probe.bin')
meta = json.loads(fixture.with_suffix('.json').read_text())
assert hashlib.sha256(fixture.read_bytes()).hexdigest() == meta['binary_sha256']
with tempfile.TemporaryDirectory(prefix='f91-vectors-') as td:
    root = Path(td)
    uart = root / 'uart.txt'
    vm = VM(fixture, 'file:' + str(uart), extra=('-icount', 'shift=0'),
            machine=meta['board'], loader='-kernel')
    try:
        for iteration in range(2):
            vm.cmd('cont')
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                text = vm.hmp('info registers')
                regs = {k: int(v, 16) for k, v in
                        re.findall(r'([A-Z0-9]+)=([0-9a-f]+)', text)}
                if regs['HALTED'] and regs['PC'] == meta['symbols']['_done'] + 1:
                    break
                time.sleep(.002)
            else:
                raise AssertionError(text)
            for key, value in {'BC': 0x123456, 'DE': 0x345678, 'HL': 0x56789a,
                               'IX': 0x789abc, 'IY': 0x9abcde, 'SPL': 0xb90000,
                               'ADL': 1, 'MADL': 1, 'IM': 2, 'IFF1': 0}.items():
                assert regs[key] == value, (key, regs)
            f = root / 'ticks.bin'
            vm.cmd('pmemsave', {'val': meta['symbols']['_ticks'], 'size': 1,
                                'filename': str(f)})
            assert f.read_bytes() == b'\x03', f.read_bytes()
            if iteration == 0:
                vm.cmd('stop')
                vm.cmd('system_reset')
    finally:
        vm.close()
    assert uart.read_bytes() == bytes.fromhex(meta['expected_uart_hex']) * 2
print('PASS: original vector init/set_vector/trampoline, three Timer0 IRQs, registers, reset')
