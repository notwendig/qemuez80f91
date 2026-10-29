#!/usr/bin/env python3
"""Run the real ZDS C fixture and verify startup and initialized memory."""
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from ez80_testlib import VM

fixture = (Path(sys.argv[2]) if len(sys.argv) > 2 else
           Path(__file__).resolve().parents[1] / 'examples/zds_cstartup/probe.bin')
meta = json.loads(fixture.with_suffix('.json').read_text())
assert hashlib.sha256(fixture.read_bytes()).hexdigest() == meta['binary_sha256']
symbols = meta['symbols']
with tempfile.TemporaryDirectory(prefix='zds-cstartup-') as td:
    root = Path(td)
    uart = root / 'uart.txt'
    vm = VM(fixture, serial='file:' + str(uart), machine=meta['board'], loader='-kernel')
    try:
        for iteration in range(2):
            vm.cmd('cont')
            vm.halted()
            regs = vm.hmp('info registers')
            pc = int(re.search(r'PC=([0-9a-f]+)', regs)[1], 16)
            assert symbols['_main'] < pc < symbols['__frameset'], regs
            for name, size, expected in (
                ('_bss_probe', 8, b'\0' * 8),
                ('_data_probe', 3, meta['expected_result'].to_bytes(3, 'little')),
                ('_result', 3, meta['expected_result'].to_bytes(3, 'little')),
            ):
                dump = root / 'dump.bin'
                vm.cmd('pmemsave', {'val': symbols[name], 'size': size,
                                    'filename': str(dump)})
                assert dump.read_bytes() == expected, (name, dump.read_bytes())
            if iteration == 0:
                vm.cmd('stop')
                vm.cmd('system_reset')
    finally:
        vm.close()
    assert uart.read_bytes() == bytes.fromhex(meta['expected_uart_hex']) * 2
print('PASS: original FreeRTOS-project C startup, real ZDS main, BSS/data, UART, reset')
