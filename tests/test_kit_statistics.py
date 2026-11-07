#!/usr/bin/env python3
"""Validate live kit telemetry without reading host process memory."""
import json
from pathlib import Path
import tempfile
import time
from ez80_testlib import VM

with tempfile.TemporaryDirectory(prefix='kit-stats-') as directory:
    root = Path(directory)
    image = root / 'loop.bin'
    image.write_bytes(bytes([0x5b, 0xc3, 5, 0, 0, 0, 0x18, 0xfd]))
    state = root / 'kit.json'
    vm = VM(image, machine='ez80f91-freertos,ram-boot=on', loader='-kernel',
            extra=('-icount', 'shift=5,sleep=off', '-nic', 'none', '-global',
                   f'ez80f91-memory.kit-led-state={state}'))
    try:
        def sample():
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    value = json.loads(state.read_text())
                    if 'instructions' in value and value.get('clock_hz', 0) > 0:
                        return value
                except (OSError, ValueError):
                    pass
                time.sleep(.02)
            raise AssertionError('No kit statistics')

        initial = sample()
        assert initial['clock_hz'] == 50000000 and not initial['running'], initial
        banks = {entry['name']: entry for entry in initial['memory']}
        assert banks['CS1']['enabled'] and banks['CS1']['end'] == 0x7ffff, banks
        assert not banks['Flash int.']['enabled'], banks
        assert banks['SRAM int.']['start'] == 0xffe000, banks
        vm.cmd('cont')
        time.sleep(.2)
        first = sample()
        time.sleep(.3)
        second = sample()
        assert second['running'] and second['icount'], second
        instructions = int(second['instructions']) - int(first['instructions'])
        virtual = int(second['virtual_ns']) - int(first['virtual_ns'])
        assert instructions > 0 and virtual == instructions * 32, (instructions, virtual)
        assert int(second['host_ns']) > int(first['host_ns'])
        vm.cmd('stop')
        time.sleep(.05)
        assert not sample()['running']
    finally:
        vm.close()
print('PASS: kit memory decoder, clock, instruction/host/guest counters and paused state')
