#!/usr/bin/env python3
"""CS0..3 decode, bank relocation, priority and AMD external NOR operations."""
from pathlib import Path
import re
import tempfile
from ez80_testlib import VM

class ROM:
    def __init__(self):
        self.b=bytearray([0x5b,0xc3,5,0,0]);self.out(0xaa,0)
    def emit(self,*data):self.b.extend(data)
    def ld(self,op,n):self.emit(op,*n.to_bytes(3,'little'))
    def out(self,port,n):self.emit(0x3e,n,0xed,0x39,port)
    def write(self,at,n):self.emit(0x3e,n);self.ld(0x32,at)
    def sample(self,at,slot):self.ld(0x3a,at);self.ld(0x32,0xffe100+slot)
    def cs(self,n,lower,upper,ctl=8):
        self.out(0xa8+3*n+2,0)
        self.out(0xa8+3*n,lower);self.out(0xa9+3*n,upper);self.out(0xaa+3*n,ctl)
    def unlock(self,base,command):
        self.write(base+0x555,0xaa);self.write(base+0x2aa,0x55);self.write(base+0x555,command)

with tempfile.TemporaryDirectory(prefix='f91-cs-') as td:
    root=Path(td)
    def run(name,r,expected,opts='',reset_expected=None):
        r.emit(0x76);path=root/(name+'.bin');path.write_bytes(r.b)
        v=VM(path,machine='ez80f91-minimal'+opts,extra=('-nic','none','-icount','shift=5'))
        try:
            for iteration,result in enumerate([expected]+([] if reset_expected is None else [reset_expected])):
                v.cmd('cont');v.halted();v.cmd('stop')
                saved=root/'mem';v.cmd('pmemsave',{'val':0xffe100,'size':len(result),'filename':str(saved)})
                assert saved.read_bytes()==bytes(result),(name,saved.read_bytes().hex(),bytes(result).hex(),v.hmp('info registers'))
                if iteration==0 and reset_expected is not None:v.cmd('system_reset')
        finally:v.close()
        print('PASS:',name)

    for n in range(4):
        r=ROM();r.cs(n,0x20,0x22);r.write(0x200123,0x50+n);r.write(0x220123,0x60+n)
        r.sample(0x200123,0);r.out(0xaa+3*n,0);r.sample(0x200123,1)
        r.out(0xa8+3*n,0x30);r.out(0xa9+3*n,0x32);r.out(0xaa+3*n,8)
        r.sample(0x300123,2);r.sample(0x320123,3)
        # Shrinking and then growing exposes the same backing bytes again.
        r.out(0xa9+3*n,0x30);r.out(0xa9+3*n,0x32);r.sample(0x320123,4)
        r.out(0xaa+3*n,0x18);r.sample(0x300123,5)
        r.out(0xa8+3*n,0x40);r.out(0xa9+3*n,0x3f);r.out(0xaa+3*n,8)
        r.sample(0x400123,6)
        # Disable all other CS devices so the absence value is unambiguous.
        run(f'CS{n}-RAM-relocate-resize-disable-IO-invalid-bounds',r,
            [0x50+n,0,0x50+n,0x60+n,0x60+n,0,0],
            ''.join(f',cs{i}='+('ram' if i==n else 'none') for i in range(4)))

    r=ROM();r.out(0xaa,0)
    for n in reversed(range(4)):
        r.cs(n,0x20,0x20);r.write(0x200100,0x10+n)
    for n in range(4):
        r.sample(0x200100,n);r.out(0xaa+3*n,0)
    run('CS0-wins-over-CS1-CS2-CS3',r,[0x10,0x11,0x12,0x13],',cs0=ram')

    r=ROM();r.cs(1,0,0xff);r.write(0xffe123,0x42);r.sample(0xffe123,0)
    r.write(0x10000,0x66);r.sample(0x10000,1) # internal ROM ignores writes
    run('internal-RAM-and-Flash-win-over-CS',r,[0x42,255],',cs0=none')

    r=ROM();r.cs(1,0x20,0x20);r.write(0x200100,0x42)
    r.cs(0,0x20,0x20);r.sample(0x200100,0)
    r.out(0xaa,0);r.sample(0x200100,1)
    run('unpopulated-CS0-still-blocks-lower-priority-RAM',r,[0,0x42],',cs0=none')

    # Program/query/erase is exercised on every CS with the same AMD bus protocol.
    for n in range(4):
        r=ROM();base=0x400000;r.cs(n,0x40,0x5f);r.sample(base+0x81234,0)
        r.unlock(base,0x90);r.sample(base,1);r.sample(base+1,2);r.write(base,0xf0)
        r.unlock(base,0xa0);r.write(base+0x81234,0x5a)
        r.sample(base+0x81234,3)
        r.out(0xa8+3*n,0x60);r.out(0xa9+3*n,0x7f);base=0x600000
        r.sample(base+0x81234,4);r.sample(base+0x181234,5) # 1 MiB chip mirror
        r.unlock(base,0xa0);r.write(base+0x81234,0x0f);r.sample(base+0x81234,6)
        r.unlock(base,0x80);r.write(base+0x555,0xaa);r.write(base+0x2aa,0x55)
        r.write(base+0x81234,0x30)
        # Poll DQ7; sector erase completes via QEMU virtual time.
        r.ld(0x3a,base+0x81234);r.emit(0xe6,0x80,0x28,0xf8)
        r.sample(base+0x81234,7)
        r.write(base+0x55,0x98)
        for i in range(3):r.sample(base+0x10+i,8+i)
        r.write(base,0xf0)
        run(f'CS{n}-AMD-ID-program-NOR-erase-mirror-relocation',r,
            [255,1,0x37,0x5a,0x5a,0x5a,0x0a,255,81,82,89],
            ''.join(f',cs{i}='+('flash' if i==n else 'none') for i in range(4)))

    r=ROM();r.cs(3,0x70,0x70);r.sample(0x700100,0)
    r.write(0x700100,0x5a);r.sample(0x700100,1)
    run('RAM-backing-survives-system-reset',r,[0,0x5a],reset_expected=[0x5a,0x5a])

    r=ROM();base=0x400000;r.cs(0,0x40,0x4f);r.sample(base+0x81234,0)
    r.unlock(base,0xa0);r.write(base+0x81234,0x5a);r.sample(base+0x81234,1)
    run('AMD-Flash-backing-survives-system-reset',r,[255,0x5a],reset_expected=[0x5a,0x5a])
