#!/usr/bin/env python3
"""Real kernel yield/critical state, delayed wakeups, idle and 24-bit rollover."""
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import time
from ez80_testlib import VM

base = Path(__file__).resolve().parents[1] / 'examples/freertos_tasks/blocking'
fixtures = ([Path(sys.argv[2])] if len(sys.argv) > 2 else
            [base / 'probe.bin', base / 'wrap.bin'])
for fixture in fixtures:
    meta = json.loads(fixture.with_suffix('.json').read_text())
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == meta['binary_sha256']
    symbols = meta['symbols']
    expected = bytes.fromhex(meta['expected_uart_hex'])
    with tempfile.TemporaryDirectory(prefix='f91-blocking-') as td:
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
        def words(name, count):
            raw = memory(symbols[name], 3 * count)
            return [int.from_bytes(raw[n:n+3], 'little') for n in range(0, len(raw), 3)]
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
                failure = number(symbols['_failure'])
                assert failure == 0, (meta['scenario'], failure, text, uart.read_bytes())
                assert number(symbols['_done']) == 1, text
                assert number(symbols['_cooperative_done']) == 1
                assert number(symbols['_event_count']) == len(expected)
                assert memory(symbols['_events'], len(expected)) == expected
                ticks = [(meta['initial_tick'] + n) & 0xffffff
                         for n in meta['expected_event_offsets']]
                assert words('_event_ticks', len(ticks)) == ticks
                assert words('_runs', 2) == [2, 4]
                assert number(symbols['_final_tick']) == ((meta['initial_tick'] + 6) & 0xffffff)
                # llport's independent uptime starts at zero even in the rollover run.
                assert number(symbols['_xTickCount']) == 6
                assert number(symbols['_idle_entries']) > 0
                assert memory(symbols['_idle_seen'], 8) == b'\x01' * 6 + b'\0\0'
                assert memory(symbols['_criticalcounter'], 1) == b'\0'
                assert regs['ADL'] == regs['MADL'] == 1 and regs['IFF1'] == 0
                current = number(symbols['_pxCurrentTCB'])
                assert current == symbols['_tcbs'] + meta['tcb_size']
                for task, guard in enumerate((0x123456, 0xabcdef, 0x654321)):
                    low = symbols['_stacks'] + task * meta['stack_words'] * 3
                    high = low + meta['stack_words'] * 3
                    tcb = symbols['_tcbs'] + task * meta['tcb_size']
                    assert low < number(tcb) < high, (task, number(tcb))
                    assert number(low) == guard, task
                    if current == tcb:
                        assert low < regs['SPL'] < high, regs
                assert uart.read_bytes() == expected * (iteration + 1)
                if iteration == 0:
                    vm.cmd('system_reset')
        finally:
            vm.close()
    print('PASS:', meta['scenario'], 'yield, nested critical state, delay/idle, exact ticks, stacks, reset')
