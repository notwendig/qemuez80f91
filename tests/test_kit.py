#!/usr/bin/env python3
"""Development-kit LED latches, decoder priority, GPIO and multiplex telemetry."""
import json
from pathlib import Path
import sys
import tempfile
import time
from ez80_testlib import VM
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/zds'))
from rsp import RSP

with tempfile.TemporaryDirectory(prefix='f91-kit-') as td:
    root=Path(td);rom=root/'halt.bin';rom.write_bytes(b'\x76')
    state=root/'leds.json';gdb=root/'gdb.sock'
    vm=VM(rom,extra=('-nic','none','-gdb',f'unix:{gdb},server=on,wait=off',
                     '-icount','shift=5,sleep=off',
                     '-global',f'ez80f91-memory.kit-led-state={state}'))
    g=RSP(unix=str(gdb))
    def io(reg,value):g.write_memory(0x1000000+reg,bytes([value]))
    def led(reg,value):g.write_memory(0x800000+reg,bytes([value]))
    def wait(check):
        end=time.monotonic()+3
        while time.monotonic()<end:
            try:
                data=json.loads(state.read_text())
                if check(data):return data
            except (ValueError,OSError):pass
            time.sleep(.025)
        raise AssertionError(data)
    try:
        wait(lambda d:not d['enabled'])
        io(0xaa,0);io(0xae,0x80);io(0xaf,0xbf);io(0xb0,0x28)
        wait(lambda d:d['enabled'])
        led(0,1);led(1,0x1e)
        wait(lambda d:int(d['mask'],16)==1<<4)
        led(1,0x0f);wait(lambda d:int(d['mask'],16)==1)
        led(0,0x7f);led(1,0);wait(lambda d:int(d['mask'],16)==(1<<35)-1)
        led(2,0x55);assert g.memory(0x800002,1)==b'\x55'
        led(0,0x80);assert g.memory(0x800002,1)==b'\xff'
        wait(lambda d:int(d['mask'],16)==0)
        io(0xad,0);io(0xab,0x80);io(0xac,0x80);io(0xad,0x28)
        wait(lambda d:not d['enabled']) # higher-priority CS1 owns these addresses
        io(0xad,0);io(0xb0,0);wait(lambda d:not d['enabled'])
        io(0xb0,0x28);wait(lambda d:d['enabled'])
        print('PASS: kit address decode, LED polarity/orientation, GPIO and CS priority')
        # Original-style 7-row multiplex scan. Switching-row ghosts must not
        # become permanent pixels in the telemetry's integrated display.
        glyph=[0x11,0x0e,0x0e,0x00,0x0e,0x0e,0x0e]
        expected=sum((1<<(row*5+col)) for row in range(7) for col in range(5)
                     if not glyph[row]&(1<<(4-col)))
        code=bytearray()
        for row,value in enumerate(glyph):
            code+=bytes([0x3e,1<<row,0x32,0,0,0x80,0x3e,value,0x32,1,0,0x80])
            code+=b'\0'*256
        code+=bytes.fromhex('c30000b8')
        g.write_memory(0xb80000,code)
        regs=g.registers();regs[0]=0xb80000;regs[18]=1;g.set_registers(regs)
        vm.cmd('cont');wait(lambda d:int(d['mask'],16)==expected);vm.cmd('stop')
        print('PASS: multiplex glyph integration without row-switch ghost pixels')
        vm.cmd('system_reset');wait(lambda d:not d['enabled'] and int(d['mask'],16)==0)
        print('PASS: kit reset clears LED latches')
    finally:g.socket.close();vm.close()
