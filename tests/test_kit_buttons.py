#!/usr/bin/env python3
"""Kit controls reach GPIO PB0..2 and their real F91 interrupt vectors."""
import json
from pathlib import Path
import sys
import tempfile
import time
from ez80_testlib import VM
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from kit import KitControls

with tempfile.TemporaryDirectory(prefix='f91-buttons-') as td:
    root=Path(td);qmp=root/'qmp.sock';rom=root/'buttons.bin'
    code=bytearray.fromhex('5bc3050000310000b9ed7d') # ADL, SPL, STMIX
    def out(port,value):code.extend((0x3e,value,0xed,0x39,port))
    def ld(op,value):code.append(op);code.extend(value.to_bytes(3,'little'))
    for bit in range(3):
        ld(0x21,0x200+bit*32);ld(0x22,0x6b0a0+bit*4)
    ld(0x21,0x6b0);code.extend(bytes.fromhex('edc7ed5e'))
    for port,value in ((0x9a,7),(0x9d,7),(0x9c,0),(0x9b,0xf8)):out(port,value)
    code.append(0xfb);loop=len(code);code.extend((0x76,0xc3));code.extend(loop.to_bytes(3,'little'))
    for bit in range(3):
        code.extend(b'\0'*(0x200+bit*32-len(code)))
        ld(0x3a,0x6b100+bit);code.append(0x3c);ld(0x32,0x6b100+bit)
        out(0xa7,1<<bit);code.extend(bytes.fromhex('fb5bed4d'))
    rom.write_bytes(code)
    vm=VM(rom,extra=('-nic','none','-icount','shift=0',
                    '-qmp',f'unix:{qmp},server=on,wait=off'),
          machine='ez80f91-freertos,ram-boot=on',loader='-kernel')
    controls=KitControls(qmp)
    def counters():
        target=root/'counts';vm.cmd('pmemsave',{'val':0x6b100,'size':3,'filename':str(target)})
        return target.read_bytes()
    def wait(expected):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            actual=counters()
            if actual==bytes(expected):return
            time.sleep(.01)
        raise AssertionError((actual,expected))
    try:
        vm.cmd('cont');vm.halted();expected=[0,0,0]
        for bit in range(3):
            controls.button(bit,True);expected[bit]+=1;wait(expected)
            result=vm.hmp('i /b 0x9a')
            assert f'0x{(0xff & ~(1<<bit)):02x}' in result,result
            controls.button(bit,False);expected[bit]+=1;wait(expected)
        time.sleep(.03);assert counters()==bytes(expected),'IRQ was not acknowledged'
        controls.button(0,True);controls.button(1,True);controls.release()
        vm.cmd('stop');controls.reset()
        assert vm.hmp('info registers').find('PC=000000')>=0
        assert '0xff' in vm.hmp('i /b 0x9a')
        print('PASS: SW1..3 active-low inputs, both-edge IRQ vectors, ALT0 ack, release and SW4 reset')
    finally:vm.close()
