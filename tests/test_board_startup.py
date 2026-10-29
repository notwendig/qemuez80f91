#!/usr/bin/env python3
"""Original F91 init_params startup, memory/PLL parameters, real tasks and reset."""
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import time
from ez80_testlib import VM

base = Path(__file__).resolve().parents[1] / 'examples/freertos_tasks/board'
fixtures = ([Path(sys.argv[2])] if len(sys.argv) > 2 else
            [base / 'probe.bin', base / 'pll.bin'])
for fixture in fixtures:
    meta = json.loads(fixture.with_suffix('.json').read_text())
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == meta['binary_sha256']
    symbols = meta['symbols']
    params = {k: int(v[1:],16) if v.startswith('$') else int(v)
              for k,v in meta['startup_parameters'].items()}
    pll = meta['scenario'] == 'pll'
    expected = [0,0,0x41 if pll else 0,0x21 if pll else 0]
    for cs in range(4):
        expected.extend(params[f'__CS{cs}_{reg}_INIT_PARAM'] for reg in ('LBR','UBR','CTL'))
    expected.extend(params[f'__RAM_{reg}_INIT_PARAM'] for reg in ('CTL','ADDR_U'))
    expected.extend(params[f'__CS{cs}_BMC_INIT_PARAM'] for cs in range(4))
    expected += [params['__FLASH_ADDR_U_INIT_PARAM'], params['__FLASH_CTL_INIT_PARAM']]
    with tempfile.TemporaryDirectory(prefix='f91-board-') as td:
        root = Path(td); uart = root / 'uart.txt'
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
                    regs = {k: int(v,16) for k,v in
                            re.findall(r'([A-Z0-9]+)=([0-9a-f]+)',text)}
                    if regs['HALTED']: break
                    time.sleep(.02)
                else:
                    raise AssertionError(text)
                vm.cmd('stop')
                assert number(symbols['_failure']) == 0, (meta['scenario'], text)
                assert memory(symbols['_startup_ports'],24) == bytes(expected)
                assert number(symbols['_startup_ok']) == 1
                # These are poisoned after checking initialization; reset must repair them.
                assert number(symbols['_startup_bss']) == 0xa5a5a5
                assert number(symbols['_startup_data']) == 0x654321
                assert 0xb8ff00 < number(symbols['_startup_sp']) < 0xb90000
                assert memory(symbols['_runs'],6) == b'\x04\0\0\x04\0\0'
                assert number(symbols['_xTickCount']) == 7
                assert memory(symbols['_criticalcounter'],1) == b'\0'
                assert regs['ADL'] == regs['MADL'] == 1 and regs['IFF1'] == 0
                current = number(symbols['_pxCurrentTCB'])
                for task,guard in enumerate((0x123456,0xabcdef)):
                    low = symbols['_stacks'] + task * meta['stack_words'] * 3
                    high = low + meta['stack_words'] * 3
                    tcb = symbols['_tcbs'] + task * meta['tcb_size']
                    assert low < number(tcb) < high
                    assert number(low) == guard
                    if current == tcb: assert low < regs['SPL'] < high
                assert current in (symbols['_tcbs'],symbols['_tcbs']+meta['tcb_size'])
                assert uart.read_bytes() == bytes.fromhex(meta['expected_uart_hex']) * (iteration+1)
                if iteration == 0: vm.cmd('system_reset')
        finally:
            vm.close()
    print('PASS:',meta['scenario'],'original board init, clock/memory, C startup, kernel tasks, reset')
