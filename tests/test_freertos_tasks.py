#!/usr/bin/env python3
"""Exercise real kernel time slicing, original context switching, and reset."""
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import time
from ez80_testlib import VM

fixture = (Path(sys.argv[2]) if len(sys.argv) > 2 else
           Path(__file__).resolve().parents[1] / 'examples/freertos_tasks/probe.bin')
meta = json.loads(fixture.with_suffix('.json').read_text())
assert hashlib.sha256(fixture.read_bytes()).hexdigest() == meta['binary_sha256']
symbols = meta['symbols']
with tempfile.TemporaryDirectory(prefix='f91-tasks-') as td:
    root = Path(td)
    uart = root / 'uart.txt'
    vm = VM(fixture, 'file:' + str(uart), extra=('-icount', 'shift=0'),
            machine=meta['board'], loader='-kernel')
    def memory(address, size):
        f = root / 'memory.bin'
        vm.cmd('pmemsave', {'val': address, 'size': size, 'filename': str(f)})
        return f.read_bytes()
    def number(address):
        return int.from_bytes(memory(address, 3), 'little')
    try:
        for iteration in range(2):
            vm.cmd('cont')
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                text = vm.hmp('info registers')
                regs = {k: int(v, 16) for k, v in
                        re.findall(r'([A-Z0-9]+)=([0-9a-f]+)', text)}
                if regs['HALTED']:
                    break
                time.sleep(.02)
            else:
                raise AssertionError(text)
            vm.cmd('stop')
            assert number(symbols['_failure']) == 0, text
            assert memory(symbols['_runs'], 6) == b'\x04\0\0\x04\0\0'
            assert number(symbols['_xTickCount']) == 7
            assert memory(symbols['_criticalcounter'], 1) == b'\0'
            assert regs['ADL'] == regs['MADL'] == 1 and regs['IFF1'] == 0
            # Both task TCBs retain SPs in their respective 1536-byte stacks.
            # The active task must also execute on its own stack, not the boot stack.
            tcb_size = meta['tcb_size']
            current = number(symbols['_pxCurrentTCB'])
            assert current in (symbols['_tcbs'], symbols['_tcbs'] + tcb_size)
            for task in range(2):
                low = symbols['_stacks'] + task * 512 * 3
                high = low + 512 * 3
                tcb = symbols['_tcbs'] + task * tcb_size
                assert low < number(tcb) < high, (task, number(tcb))
                assert number(low) == (0x123456, 0xabcdef)[task], task
                if current == tcb:
                    assert low < regs['SPL'] < high, regs
            assert uart.read_bytes() == b'BABABABA!' * (iteration + 1)
            if iteration == 0:
                vm.cmd('system_reset')
    finally:
        vm.close()
print('PASS: two real FreeRTOS tasks, seven preemptive ticks, separate stacks, reset')
