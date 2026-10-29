#!/usr/bin/env python3
"""Basic reset, halt and invalid-ROM integration checks."""
import pathlib
import subprocess
import tempfile
from ez80_testlib import VM, binary

with tempfile.TemporaryDirectory(prefix='ez80-smoke-') as td:
    d = pathlib.Path(td)
    rom = d/'nop-halt.bin'
    rom.write_bytes(bytes([0x00, 0x00, 0x76, 0xff]))
    vm = VM(rom)
    try:
        regs = vm.hmp('info registers')
        assert 'PC=000000 ADL=0 MBASE=00 MADL=0' in regs, regs
        assert 'SPS=0000 SPL=000000 I=0000 R=00 IFF1=0 IFF2=0' in regs, regs
        vm.cmd('cont')
        vm.halted()
        regs = vm.hmp('info registers')
        assert 'PC=000003' in regs and 'R=03' in regs, regs
        vm.cmd('stop')
        vm.cmd('system_reset')
        regs = vm.hmp('info registers')
        assert 'PC=000000 ADL=0 MBASE=00 MADL=0' in regs and 'R=00' in regs, regs
        vm.cmd('cont')
        vm.halted()
        assert 'PC=000003' in vm.hmp('info registers')
    finally:
        vm.close()
    print('PASS: reset, two NOPs, HALT, no execution after HALT, reset/re-execution')

    # Reserved CPU encodings generate hardware TRAPs, covered by
    # test_illegal_traps.py rather than terminating the emulator process.

    for name, data in [('empty.bin', b''), ('oversize.bin', b'\x00' * (256*1024+1))]:
        f = d/name
        f.write_bytes(data)
        p = subprocess.run([binary, '-M', 'ez80f91-minimal', '-bios', str(f),
                            '-display', 'none', '-serial', 'none', '-monitor', 'none'],
                           capture_output=True, timeout=10)
        assert p.returncode != 0, name
    print('PASS: empty and oversized ROMs rejected')
