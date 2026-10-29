#!/usr/bin/env python3
"""F91 shared-RAM MAC through a real QEMU Ethernet socket backend."""
import pathlib
import socket
import struct
import sys
import tempfile
import time
import zlib
from ez80_testlib import VM
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from tools.zds.rsp import RSP

MAC = bytes.fromhex('525400123456')
FRAME = MAC + bytes.fromhex('0200000000010800') + bytes(range(46))

class Fixture:
    def __init__(self, root):
        self.root = root
        rom = root/'mac.bin'; rom.write_bytes(bytes([0x5b, 0xc3, 5, 0, 0, 0x76]))
        self.host, peer = socket.socketpair()
        self.host.settimeout(3)
        path = root/'gdb.sock'
        self.vm = VM(rom, extra=('-nic', f'socket,id=wire,fd={peer.fileno()}',
                                 '-gdb', f'unix:{path},server=on,wait=off'),
                     pass_fds=(peer.fileno(),))
        peer.close()
        self.g = RSP.__new__(RSP)
        self.g.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.g.socket.settimeout(3); self.g.socket.connect(str(path)); self.g.running = False
        self.g.command('?')
        self.vm.cmd('cont'); self.vm.halted(); self.vm.cmd('stop')
    def read(self, at, n=1): return self.g.memory(at, n)
    def write(self, at, data): self.g.write_memory(at, bytes(data))
    def io(self, reg, value=None):
        if value is None: return self.read(0x1000000 + reg)[0]
        self.write(0x1000000 + reg, [value])
    def word(self, reg): return self.io(reg) | self.io(reg+1) << 8
    def setup(self, base=0xff, start=0x1000, end=0x2000, block=0):
        self.io(0x41, 0x3f); self.io(0xb5, base)
        for reg, value in [(0x42,0), (0x44,start), (0x47,end), (0x49,start)]:
            self.io(reg, value & 255); self.io(reg+1, value >> 8)
        self.io(0x4b,block)
        for i,b in enumerate(MAC): self.io(0x25+i,b)
        self.io(0x21,0x98); self.io(0x24,1); self.io(0x32,1)
        self.io(0x41,0); self.io(0x4d,255)
        self.base = base << 16 | 0xc000
    def tx(self, frame=FRAME, at=0, next_at=0x100, kick=True):
        self.write(self.base+at, (self.base+next_at).to_bytes(3,'little') +
                   struct.pack('<HH',len(frame),0x8000) + frame)
        if kick: self.io(0x40,0)
    def packet(self):
        def exact(n):
            data=b''
            while len(data)<n: data+=self.host.recv(n-len(data))
            return data
        self.vm.cmd('cont')
        try: return exact(struct.unpack('!I',exact(4))[0])
        finally: self.vm.cmd('stop')
    def inject(self, frame):
        self.vm.cmd('cont')
        self.host.sendall(struct.pack('!I',len(frame))+frame)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            time.sleep(.01); self.vm.cmd('stop')
            if self.io(0x4d)&0xc: return
            self.vm.cmd('cont')
        raise AssertionError('RX timeout')
    def phy(self, reg, value=None, addr=0):
        self.io(0x3e,reg); self.io(0x3f,addr)
        if value is not None:
            self.io(0x3c,value&255); self.io(0x3d,value>>8); self.io(0x3b,0x80)
        self.io(0x3b,0x40)
        return self.word(0x4e)
    def close(self): self.g.socket.close(); self.host.close(); self.vm.close()

with tempfile.TemporaryDirectory(prefix='f91-emac-') as td:
    f=Fixture(pathlib.Path(td))
    try:
        assert f.io(0x41)==0x20 and f.word(0x30)==1536
        f.setup()
        f.tx(); assert f.packet()==FRAME
        assert f.read(f.base+5,2)==b'\0\0' and f.word(0x53)==0x100
        assert f.io(0x4d)==1
        f.io(0x4d,1); assert f.io(0x4d)==0
        print('PASS: real backend TX, ownership, TRP and W1C')
        f.inject(FRAME)
        received=f.read(f.base+0x1000,71)
        assert received[:7]==bytes.fromhex('00d1ff40000080'),received.hex()
        assert received[7:67]==FRAME
        assert received[67:71]==struct.pack('<I',zlib.crc32(FRAME))
        assert f.word(0x51)==0x1100 and f.word(0x55)==14
        print('PASS: backend RX descriptor, FCS and free blocks')
        assert f.phy(2)==0x22 and f.phy(3)==0x561b
        assert f.phy(1)&0x24==0x24 and f.io(0x4d)&0x40
        assert f.phy(2,addr=7)==0xffff
        assert f.phy(0,0x8000)==0x3100
        assert f.phy(0,0x3900)==0x3900 and f.phy(1)&4==0
        f.phy(0,0x3100)
        f.vm.cmd('set_link',{'name':'wire','up':False})
        assert f.phy(1)&4==0 and f.io(0x50)&0x40
        f.vm.cmd('set_link',{'name':'wire','up':True})
        assert f.phy(1)&4
        print('PASS: PHY IDs, management IRQ, reset, power-down and link')
        f.setup(base=0xb7)
        assert f.io(0x46)==0xb7
        f.io(0x46,0xaa); assert f.io(0x46)==0xb7
        f.tx(); assert f.packet()==FRAME
        f.io(0xb4,0x80); f.io(0x4d,255)
        f.vm.cmd('cont'); f.host.sendall(struct.pack('!I',len(FRAME))+FRAME); time.sleep(.03); f.vm.cmd('stop')
        assert f.io(0x4d)==0 and f.word(0x51)==0x1000
        f.io(0xb4,0xc0)
        print('PASS: Ethernet RAM relocation, BP_U mirror and RAM enable')
        # Two-block RX ring: one packet consumes the only available block.
        f.setup(start=0x1000,end=0x1200)
        f.inject(FRAME); f.io(0x4d,8); f.inject(FRAME)
        assert f.io(0x4d)==0xc
        overrun=f.read(f.base+0x1100,7)
        assert int.from_bytes(overrun[:3],'little')==f.base+0x1000
        assert int.from_bytes(overrun[3:5],'little')==0
        assert int.from_bytes(overrun[5:],'little')==1 # RxOVR, not RxOK
        assert f.word(0x51)==0x1000
        # Original driver drains the final descriptor, acknowledges RXDONE and
        # RxOVR, then releases that descriptor via RRP. No overrun IRQ required.
        f.io(0x49,0); f.io(0x4a,0x10)
        f.io(0x4d,0xc); f.inject(FRAME)
        assert f.word(0x51)==0x1100 and f.io(0x4d)==8
        assert f.read(f.base+0x1000+7,len(FRAME))==FRAME
        print('PASS: RX overrun descriptor, Zilog driver recovery and ring wrap')
        f.setup(); f.io(0x21,0x18)
        f.tx(FRAME[:20]); assert f.packet()==FRAME[:20]
        f.io(0x41,0x14); f.io(0x41,0); f.io(0x21,0x98)
        f.tx(FRAME[:20]); assert f.packet()==FRAME[:20]+bytes(40)
        f.io(0x41,0x14); f.io(0x41,0); f.io(0x21,8)
        f.tx(FRAME+struct.pack('<I',zlib.crc32(FRAME))); assert f.packet()==FRAME
        f.io(0x41,0x14); f.io(0x41,0)
        f.tx(FRAME+bytes(4)); assert f.read(f.base+5,2)==bytes.fromhex('0042')
        print('PASS: padding, supplied CRC, bad CRC completion')
        f.setup(); f.tx(next_at=0x1800)
        assert f.io(0x4d)&0x80 and f.read(f.base+5,2)==b'\0@'
        f.io(0x4d,255); f.tx(); assert f.read(f.base+5,2)==b'\0\x80'
        f.io(0x41,0x14); f.io(0x41,0); f.io(0x40,0)
        assert f.packet()==FRAME
        print('PASS: invalid descriptor fails safely and requires TX reset')
        f.setup(); f.tx(next_at=0xf00); assert f.packet()==FRAME
        wrapped=FRAME+bytes(240)
        desc=(f.base+0x200).to_bytes(3,'little')+struct.pack('<HH',len(wrapped),0x8000)
        f.write(f.base+0xf00,desc+wrapped[:249]); f.write(f.base,wrapped[249:])
        f.io(0x40,0); assert f.packet()==wrapped and f.word(0x53)==0x200
        print('PASS: TX payload wraps within TX partition')
        f.setup()
        def drop(frame):
            f.vm.cmd('cont');f.host.sendall(struct.pack('!I',len(frame))+frame)
            time.sleep(.02);f.vm.cmd('stop')
            assert f.io(0x4d)==0 and f.word(0x51)==0x1000
        other=bytes.fromhex('020000000002')+FRAME[6:]
        drop(other)
        f.io(0x32,0);drop(bytes([255])*6+FRAME[6:])
        f.io(0x32,8);f.inject(other)
        f.setup(); multicast=bytes.fromhex('01005e000001')+FRAME[6:]
        drop(multicast)
        crc=0xffffffff
        for octet in multicast[:6]:
            for bit in range(8):
                carry=((crc>>31)^ (octet>>bit))&1
                crc=(crc<<1)&0xffffffff
                if carry: crc^=0x04c11db7
        h=crc>>26
        f.io(0x33+h//8,1<<(h%8));f.io(0x32,2);f.inject(multicast)
        assert f.read(f.base+0x1005,2)==bytes.fromhex('0082')
        f.setup();f.io(0x32,4);f.inject(multicast)
        print('PASS: unicast, broadcast, promiscuous and multicast hash filters')

    finally: f.close()

# These probes execute IN0/OUT0, descriptor writes and IM2 dispatch in the CPU.
class ROM:
    def __init__(self): self.b=bytearray([0x5b,0xc3,5,0,0])
    def emit(self,*data): self.b.extend(data)
    def ld(self,op,value): self.emit(op,*value.to_bytes(3,'little'))
    def out(self,port,value): self.emit(0x3e,value,0xed,0x39,port)
    def store(self,at,data):
        for i,value in enumerate(data): self.emit(0x3e,value); self.ld(0x32,at+i)
    def setup(self):
        self.out(0x41,0x3f)
        for reg,val in [(0x42,0),(0x43,0),(0x44,0),(0x45,0x10),
                        (0x47,0),(0x48,0),(0x49,0),(0x4a,0x10),
                        (0x21,0x98),(0x24,1),(0x32,9)]: self.out(reg,val)
        for i,b in enumerate(MAC): self.out(0x25+i,b)
        self.out(0x41,0)
    def irq(self,source,enable):
        self.ld(0x31,0xfff000); self.ld(0x21,0xffe000)
        self.ld(0x22,0xffe040+4*source)
        self.ld(0x21,0xffe1); self.emit(0xed,0xc7,0xed,0x5e)
        self.store(0xffe000,bytes([0xed,0x38,0x4d,0x32,0,0xe2,0xff,
                                    0xed,0x39,0x4d,0xf3,0x76]))
        self.out(0x4c,enable)
        self.emit(0xfb,0)

with tempfile.TemporaryDirectory(prefix='f91-emac-guest-') as td:
    root=pathlib.Path(td)
    for mode,source in enumerate([0,1,2,1]):
        r=ROM();r.setup()
        if source<2:
            r.out(0x20,1) # MAC loopback: guest TX feeds RX, no host needed
        if source in (0,1):
            r.store(0xffc000,bytes.fromhex('00c1ff3c000000')+FRAME)
        r.irq(source,[8,1,0x40][source])
        if source<2:
            if mode==3: r.out(0x40,1)
            r.store(0xffc006,b'\x80')
            if mode!=3: r.out(0x40,0)
        else: r.out(0x3e,2);r.out(0x3b,0x40)
        r.emit(0x76)
        path=root/'irq.bin';path.write_bytes(r.b)
        v=VM(path,extra=('-nic','none'))
        try:
            v.cmd('cont')
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                regs=v.hmp('info registers')
                if 'PC=ffe00c' in regs and 'HALTED=1' in regs: break
                time.sleep(.01)
            else: raise AssertionError(('MAC IRQ not dispatched',source,regs))
            v.cmd('stop');saved=root/'irq.dat'
            v.cmd('pmemsave',{'val':0xffe200,'size':1,'filename':str(saved)})
            assert saved.read_bytes()[0]&[8,1,0x40][source]
        finally:v.close()
        print('PASS: guest IM2 MAC '+(['RX','TX','system'][source] if mode!=3 else 'periodic TX polling')+' interrupt')
