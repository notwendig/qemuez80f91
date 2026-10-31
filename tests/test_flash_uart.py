#!/usr/bin/env python3
"""Guest execution tests for Flash information-page I/O and UART0 interrupts."""
from pathlib import Path
import re
import tempfile
import time
from ez80_testlib import VM

class ROM:
    def __init__(self): self.b=bytearray([0x5b,0xc3,5,0,0])
    def emit(self,*values):self.b.extend(values)
    def ld(self,op,value):self.emit(op,*value.to_bytes(3,'little'))
    def out(self,port,value):self.emit(0x3e,value,0xed,0x39,port)
    def sample(self,port,slot):self.emit(0xed,0x38,port);self.ld(0x32,0xffe100+slot)
    def write(self,at,data):
        for i,b in enumerate(data):self.emit(0x3e,b);self.ld(0x32,at+i)
    def irq(self,vector,handler):
        self.ld(0x31,0xfff000);self.ld(0x21,0xffe000);self.ld(0x22,0xffe000+vector)
        self.ld(0x21,0xffe1);self.emit(0xed,0xc7,0xed,0x5e)
        self.write(0xffe000,handler)
    def pins(self):
        self.out(0xa3,255);self.out(0xa4,0);self.out(0xa5,3);self.out(0xc3,3)

with tempfile.TemporaryDirectory(prefix='f91-flash-uart-') as td:
    root=Path(td)
    def run(name,r,expected,reset_expected=None,final_pc=None):
        path=root/(name+'.bin');path.write_bytes(r.b)
        v=VM(path,extra=('-nic','none','-icount','shift=0'),cwd=root)
        try:
            for result in [expected]+([] if reset_expected is None else [reset_expected]):
                v.cmd('cont');deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    regs=v.hmp('info registers')
                    if 'HALTED=1' in regs and (final_pc is None or f'PC={final_pc:06x}' in regs):break
                    time.sleep(.005)
                else:raise AssertionError((name,regs))
                v.cmd('stop');out=root/'sample.bin'
                v.cmd('pmemsave',{'val':0xffe100,'size':len(result),'filename':str(out)})
                assert out.read_bytes()==result,(name,out.read_bytes().hex(),result.hex(),regs)
                if reset_expected is not None and result is expected:v.cmd('system_reset')
        finally:v.close()
        print('PASS:',name)

    r=ROM();r.out(0xfc,0x80);r.out(0xfd,0);r.out(0xfe,0)
    r.sample(0xf6,0);r.out(0xfe,0);r.out(0xf6,0x5a)
    r.out(0xfe,0);r.out(0xf6,0x0f);r.out(0xfe,0);r.sample(0xf6,1)
    r.emit(0x76)
    run('info-NOR-program-and-reset-persistence',r,b'\xff\x0a',b'\x0a\x0a')

    r=ROM();r.out(0xfc,0x80);r.out(0xfd,0);r.out(0xfe,255)
    r.out(0xf6,0x12);r.out(0xf6,0x34)
    r.sample(0xfd,0);r.sample(0xfe,1)
    r.out(0xfd,0);r.out(0xfe,255);r.sample(0xf6,2);r.sample(0xf6,3)
    r.out(0xfd,1);r.out(0xfe,255);r.out(0xf6,0x56)
    r.sample(0xfd,4);r.sample(0xfe,5)
    r.out(0xff,2);r.sample(0xff,6);r.sample(0xfb,7);r.sample(0xfb,8)
    r.out(0xfd,0);r.out(0xfe,255);r.sample(0xf6,9);r.sample(0xf6,10)
    r.out(0xff,4);r.out(0xfe,255);r.out(0xf6,0x99)
    r.sample(0xff,11);r.sample(0xfb,12);r.emit(0x76)
    run('info-address-wrap-page-erase-row-done-and-status-clear',r,
        bytes([1,1,0x12,0x34,0,0,0,0x20,0,255,255,0,0x20]))

    r=ROM();r.out(0xf9,0x55);r.sample(0xf9,0);r.sample(0xfa,1)
    r.out(0xf5,0xb6);r.out(0xf5,0x49);r.out(0xf9,0x55);r.sample(0xf9,2)
    r.out(0xfa,0);r.sample(0xfa,3)
    r.out(0xf5,0xb6);r.out(0xf5,0x49);r.out(0xfa,0);r.sample(0xfa,4)
    r.out(0xf5,0xb6);r.out(0xf5,0x49);r.out(0xfa,1)
    r.out(0xfc,0);r.out(0xff,2);r.sample(0xfb,5);r.emit(0x76)
    # PS019217 Table 40: FLASH_FDIV resets to 01h; locked writes preserve it.
    run('flash-key-unlock-relock-and-protected-page-rejection',r,bytes([1,255,0x55,255,0,2]))

    r=ROM();r.irq(0x50,bytes([0xed,0x38,0xfb,0x32,0,0xe1,0xff,0xf3,0x76]))
    r.out(0xfb,0x80);r.out(0xfc,0x80);r.out(0xff,2);r.emit(0xfb,0,0x76)
    run('flash-done-IM2-vector-50',r,b'\xa0',final_pc=0xffe009)

    r=ROM();r.pins();r.out(0xc4,0x10);r.out(0xc1,3)
    r.sample(0xc2,0);r.sample(0xc2,1)
    r.out(0xc0,0x5a);r.sample(0xc2,2);r.sample(0xc5,3);r.sample(0xc0,4)
    r.sample(0xc2,5);r.sample(0xc2,6);r.out(0xc2,1)
    r.out(0xc0,0x31);r.out(0xc0,0x32);r.sample(0xc0,7);r.sample(0xc0,8)
    r.out(0xc2,7);r.sample(0xc5,9);r.sample(0xc2,10);r.emit(0x76)
    run('uart-TX-ack-RX-priority-loopback-and-FIFO-reset',r,
        bytes([2,1,4,0x61,0x5a,2,1,0x31,0x32,0x60,0x82]))

    r=ROM();r.pins();r.out(0xc4,0x10);r.out(0xc2,0xc1)
    r.out(0xc1,1);r.out(0xc0,0x5a);r.sample(0xc2,0)
    # Four character-times must elapse before an under-trigger timeout IRQ.
    r.ld(0x01,20000);r.emit(0x0b,0x78,0xb1,0x20,0xfb)
    r.sample(0xc2,1);r.sample(0xc0,2);r.sample(0xc2,3)
    for i in range(17):r.out(0xc0,i)
    r.out(0xc1,5);r.sample(0xc2,4);r.sample(0xc5,5);r.sample(0xc2,6)
    r.out(0xc2,3);r.sample(0xc5,7);r.emit(0x76)
    run('uart-FIFO-timeout-overrun-and-line-status-priority',r,
        bytes([0x81,0x8c,0x5a,0x81,0x86,0x63,0x84,0x60]))

    for kind in ['TX','RX']:
        r=ROM();r.pins();r.out(0xc4,0x10)
        # ISR records IIR, disables UART interrupts and halts.
        r.irq(0x70,bytes([0xed,0x38,0xc2,0x32,0,0xe1,0xff,0xaf,0xed,0x39,0xc1,0xf3,0x76]))
        if kind=='RX':r.out(0xc0,0x5a)
        r.out(0xc1,2 if kind=='TX' else 1);r.emit(0xfb,0,0x76)
        run('uart-'+kind+'-IM2-vector-70',r,bytes([2 if kind=='TX' else 4]),final_pc=0xffe00d)
