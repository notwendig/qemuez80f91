#!/usr/bin/env python3
"""ROM-level eZ80 mode, register, stack and UART integration tests."""
import pathlib
import re
import sys
import socket
import tempfile
from ez80_testlib import VM

class ROM:
    def __init__(self):
        self.b = bytearray()
    def emit(self, *bs):
        self.b.extend(bs)
    def imm(self, n, size=3):
        self.b.extend(n.to_bytes(size, 'little'))
    def adl(self):
        self.emit(0x5b, 0xc3, 5, 0, 0)
    def ld(self, opcode, n, prefix=(), size=3):
        self.emit(*prefix, opcode)
        self.imm(n, size)
    def out(self, port, value):
        self.emit(0x3e, value, 0xed, 0x39, port)
    def patch(self, offset, n, size=3):
        self.b[offset:offset+size] = n.to_bytes(size, 'little')

def regs(vm):
    return {k: int(v, 16) for k,v in re.findall(r'([A-Z0-9]+)=([0-9a-f]+)', vm.hmp('info registers'))}

def run(d, name, rom, expected, serial='none', memory=(), extra=()):
    path=d/(name+'.bin')
    path.write_bytes(rom.b if isinstance(rom, ROM) else rom)
    vm=VM(path,serial,extra)
    try:
        vm.cmd('cont')
        vm.halted()
        got=regs(vm)
        for k,v in expected.items():
            assert got[k]==v,(name,k,hex(v),got)
        for addr,data in memory:
            f=d/'memory.bin'
            vm.cmd('pmemsave',{'val':addr,'size':len(data),'filename':str(f)})
            assert f.read_bytes()==data,(name,hex(addr),f.read_bytes(),data)
    finally:
        vm.close()
    print('PASS:',name)

with tempfile.TemporaryDirectory(prefix='ez80-stage2-') as td:
    d=pathlib.Path(td)
    r=ROM();r.adl();r.ld(0x31,0xfffff0)
    r.ld(0x01,0x123456);r.emit(0xc5);r.ld(0x01,0);r.emit(0xd1)
    r.ld(0x21,0xa1b2c3,prefix=(0xdd,));r.emit(0xdd,0xe5,0xfd,0xe1)
    r.emit(0x3e,0x5a,0xaf,0x3e,0x5a,0xf5,0xaf,0xf1,0x76)
    run(d,'adl-registers-and-stack',r,{'ADL':1,'DE':0x123456,'IX':0xa1b2c3,
        'IY':0xa1b2c3,'AF':0x5a44,'SPL':0xfffff0},
        memory=[(0xffffed,bytes([0x44,0x5a,0]))])

    # All four suffixes fetch different immediate widths without changing ADL.
    r=ROM();r.adl();r.ld(0x21,0x123456,prefix=(0x5b,))
    r.ld(0x01,0xabcdef,prefix=(0x52,))
    r.ld(0x11,0x4567,prefix=(0x49,),size=2)
    r.ld(0x21,0x89ab,prefix=(0x40,),size=2);r.emit(0x76)
    run(d,'single-instruction-width-prefixes',r,
        {'ADL':1,'BC':0xcdef,'DE':0x4567,'HL':0x89ab})

    # CALL/RET keep a three-byte return address and preserve neighbouring bytes.
    r=ROM();r.adl();r.ld(0x31,0xfffff0);r.emit(0xcd);patch=len(r.b);r.imm(0)
    return_pc=len(r.b);r.emit(0x76);target=len(r.b);r.patch(patch,target)
    r.ld(0x01,0x987654);r.emit(0xc9)
    run(d,'adl-call-ret',r,{'BC':0x987654,'SPL':0xfffff0,'PC':return_pc+1},
        memory=[(0xffffed,return_pc.to_bytes(3,'little'))])

    # Execute a Z80-mode subroutine from RAM in MBASE FF, with a short stack.
    short=bytes([0x31,0xf0,0xff,0x01,0x34,0x12,0xc5,0xd1,0x76])
    r=ROM();r.adl()
    for i,b in enumerate(short):
        r.emit(0x3e,b);r.ld(0x32,0xffe000+i)
    r.emit(0x3e,0xff,0xed,0x6d,0x40,0xc3,0x00,0xe0)
    run(d,'z80-mbase-short-stack',r,{'ADL':0,'MBASE':0xff,'DE':0x1234,
        'SPS':0xfff0,'SPL':0,'PC':0xffe009},
        memory=[(0xffffee,bytes([0x34,0x12]))])

    # A short stack override in ADL uses SPS/MBASE and does not change SPL/ADL.
    r=ROM();r.adl();r.ld(0x31,0xffffc0)
    r.ld(0x31,0xfff0,prefix=(0x40,),size=2)
    r.emit(0x3e,0xff,0xed,0x6d);r.ld(0x01,0x112233)
    r.emit(0x52,0xc5,0x52,0xd1,0x76)
    run(d,'adl-short-stack-override',r,{'ADL':1,'SPS':0xfff0,'SPL':0xffffc0,
        'DE':0x2233},memory=[(0xffffee,b'\x33\x22')])

    # Mixed call ADL -> Z80 (CALL.IS) -> ADL (RET.L), including split stacks.
    short=bytes([0x01,0x78,0x56,0x49,0xc9])
    r=ROM();r.adl();r.ld(0x31,0xffffc0)
    r.ld(0x31,0xfff0,prefix=(0x40,),size=2)
    for i,b in enumerate(short):
        r.emit(0x3e,b);r.ld(0x32,0xffe000+i)
    r.emit(0x3e,0xff,0xed,0x6d,0xed,0x7d,0x49,0xcd,0x00,0xe0)
    ret=len(r.b);r.emit(0x76)
    run(d,'mixed-call-adl-to-z80-return',r,{'ADL':1,'MADL':1,'BC':0x5678,
        'SPS':0xfff0,'SPL':0xffffc0,'PC':ret+1},
        memory=[(0xffffbe,b'\x03\x00'),(0xffffee,ret.to_bytes(2,'little'))])

    # Mixed call Z80 -> ADL -> Z80: return frame lives wholly on SPL.
    short=bytes([0xed,0x7d,0x52,0xcd,0x00,0x01,0x00,0x76])
    r=ROM();r.adl();r.ld(0x31,0xffffc0)
    for i,b in enumerate(short):
        r.emit(0x3e,b);r.ld(0x32,0xffe000+i)
    r.emit(0x3e,0xff,0xed,0x6d,0x40,0xc3,0x00,0xe0)
    r.b.extend(b'\xff'*(0x100-len(r.b)))
    r.ld(0x01,0x2468ac);r.emit(0x5b,0xc9)
    run(d,'mixed-call-z80-to-adl-return',r,{'ADL':0,'BC':0x2468ac,
        'SPL':0xffffc0,'PC':0xffe008},memory=[(0xffffbd,b'\x02\x07\xe0')])

    # Z80 code fetch wraps at 64 KiB while operands are being fetched.
    r=bytearray(b'\xff'*0x10000)
    r[:4]=bytes([0xc3,0xfe,0xff,0x76]);r[0xfffe:]=bytes([0x21,0x34])
    run(d,'z80-instruction-fetch-wrap',r,{'ADL':0,'HL':0xc334,'PC':4})

    # ADL code crosses 64 KiB linearly, without a Z80 wrap.
    r=ROM();r.emit(0x5b,0xc3,0xfe,0xff,0)
    r.b.extend(b'\xff'*(0xfffe-len(r.b)))
    r.ld(0x21,0x123456);r.emit(0x76)
    run(d,'adl-linear-fetch-boundary',r,{'ADL':1,'HL':0x123456,'PC':0x10003})

    # Functional UART: DLAB writes must not appear as characters; mux/clock gate TX.
    r=ROM();r.adl();r.out(0xc3,3);r.out(0xc0,ord('X')) # mux still disabled
    r.out(0xa3,0xff);r.out(0xa4,0);r.out(0xa5,3)
    r.out(0xc3,0x83);r.out(0xc0,ord('X'));r.out(0xc1,ord('Y'))
    r.emit(0xed,0x00,0xc0,0xed,0x08,0xc1) # read divisors into B/C
    r.out(0xc3,3);r.out(0xdb,1);r.out(0xc0,ord('X'));r.out(0xdb,0)
    r.out(0xdb,0x80);r.out(0xc0,ord('X'));r.out(0xdb,0)
    r.out(0xc7,0xa5);r.emit(0xed,0x10,0xc7) # scratch -> D
    for b in b'Hello eZ80F91\r\n':
        # Poll THRE; JR Z back to IN0.
        r.emit(0xed,0x38,0xc5,0xe6,0x20,0x28,0xf9)
        r.out(0xc0,b)
    r.emit(0x76)
    out=d/'uart.txt'
    run(d,'uart0-dlab-mux-clock-console',r,{'BC':0x5859,'DE':0xa500},
        serial='file:'+str(out),extra=('-icount','shift=0'))
    assert out.read_bytes()==b'Hello eZ80F91\r\n',out.read_bytes()
    print('PASS: exact UART0 output, no leaked divisor or gated characters')

    # Real character-backend input, not register injection.
    r=ROM();r.adl();r.out(0xc3,3);r.out(0xa5,3)
    r.emit(0xed,0x38,0xc5,0xe6,1,0x28,0xf9)
    r.emit(0xed,0x38,0xc0);r.ld(0x32,0xffe100)
    r.emit(0xed,0x00,0xc5,0x76)
    path=d/'rx.bin';path.write_bytes(r.b)
    sockpath=d/'uart.sock'
    vm=VM(path,'unix:'+str(sockpath)+',server=on,wait=off')
    try:
        with socket.socket(socket.AF_UNIX) as sock:
            sock.connect(str(sockpath));vm.cmd('cont');sock.sendall(b'Z')
            vm.halted();got=regs(vm)
            assert got['AF']==0x5a04 and got['BC']==0x6000,got
    finally:
        vm.close()
    print('PASS: UART0 receives from socket, clears DR on RBR read')

    # Same-mode qualified CALL/RET still have mixed-frame markers.
    r=ROM();r.adl();r.ld(0x31,0xfffff0);r.emit(0xed,0x7d,0x5b,0xcd)
    fix=len(r.b);r.imm(0);ret=len(r.b);r.emit(0x76)
    r.patch(fix,len(r.b));r.emit(0x5b,0xc9)
    run(d,'mixed-call-adl-to-adl-return',r,{'ADL':1,'SPL':0xfffff0},
        memory=[(0xffffec,b'\x03'+ret.to_bytes(3,'little'))])

    # Return address high byte must survive ADL -> Z80 -> ADL.
    r=ROM();r.adl();r.ld(0x31,0xffffc0)
    r.ld(0x31,0xfff0,prefix=(0x40,),size=2)
    for i,b in enumerate(bytes([0x49,0xc9])):
        r.emit(0x3e,b);r.ld(0x32,0xffe000+i)
    r.emit(0x3e,0xff,0xed,0x6d,0xed,0x7d)
    r.emit(0xc3,0,0,1);r.b.extend(b'\xff'*(0x10000-len(r.b)))
    r.emit(0x49,0xcd,0,0xe0,0x76)
    run(d,'mixed-return-high-byte',r,{'ADL':1,'PC':0x10005,
        'SPS':0xfff0,'SPL':0xffffc0},
        memory=[(0xffffbe,b'\x03\x01'),(0xffffee,b'\x04\x00')])

    # A three-byte push starting at 0 wraps to FFFFFD and pops to 0.
    r=ROM();r.adl();r.ld(0x31,0);r.ld(0x01,0xabcdef);r.emit(0xc5,0xd1,0x76)
    run(d,'adl-stack-address-wrap',r,{'ADL':1,'SPL':0,'DE':0xabcdef},
        memory=[(0xfffffd,b'\xef\xcd\xab')])

    # Absolute memory transfers are three bytes, not an accidental 32-bit store.
    r=ROM();r.adl();r.ld(0x21,0x123456);r.ld(0x22,0xffe200)
    r.ld(0x21,0);r.ld(0x2a,0xffe200);r.emit(0x76)
    run(d,'24-bit-memory-transfer-width',r,{'HL':0x123456},
        memory=[(0xffe200,b'\x56\x34\x12\x00')])

    # Long stack override in Z80 mode selects SPL, independent of SPS/MBASE.
    short=bytes([0x49,0xc5,0x49,0xd1,0x76])
    r=ROM();r.adl();r.ld(0x31,0xffffc0);r.ld(0x01,0x123456)
    for i,b in enumerate(short):
        r.emit(0x3e,b);r.ld(0x32,0xffe000+i)
    r.emit(0x3e,0xff,0xed,0x6d,0x40,0xc3,0,0xe0)
    run(d,'z80-long-stack-override',r,{'ADL':0,'DE':0x123456,
        'SPL':0xffffc0,'SPS':0},memory=[(0xffffbd,b'\x56\x34\x12')])

    # Register-indirect JP changes mode, and LD MB,A is a NOP in Z80 mode.
    r=ROM();r.adl();r.ld(0x21,0xffe000,prefix=(0xdd,))
    for i,b in enumerate(bytes([0x3e,0,0xed,0x6d,0x76])):
        r.emit(0x3e,b);r.ld(0x32,0xffe000+i)
    r.emit(0x3e,0xff,0xed,0x6d,0x52,0xdd,0xe9)
    run(d,'indirect-jp-and-short-mbase-nop',r,{'ADL':0,'MBASE':0xff,
        'PC':0xffe005,'IX':0xffe000})

    # Normal Z80 CALL/RET use two bytes on SPS in the MBASE bank.
    short=bytearray([0x31,0xf0,0xff,0xcd,0x10,0xe0,0x76])
    short.extend(b'\x00'*(0x10-len(short)))
    short.extend([0x01,0x78,0x56,0xc9])
    r=ROM();r.adl()
    for i,b in enumerate(short):
        r.emit(0x3e,b);r.ld(0x32,0xffe000+i)
    r.emit(0x3e,0xff,0xed,0x6d,0x40,0xc3,0,0xe0)
    run(d,'z80-call-ret',r,{'ADL':0,'BC':0x5678,'SPS':0xfff0,
        'PC':0xffe007},memory=[(0xffffee,b'\x06\xe0')])

    # Relative branch fetch at FFFFFF wraps into flash at 000000.
    r=ROM();r.adl();r.emit(0x3e,0x18);r.ld(0x32,0xffffff)
    r.emit(0xc3,0xff,0xff,0xff)
    r.b.extend(b'\xff'*(0x5c-len(r.b)));r.emit(0x76)
    run(d,'adl-instruction-fetch-wrap',r,{'ADL':1,'PC':0x5d})

    # A system reset restores the UART bank selector, divisor, scratch and GPIO.
    r=ROM();r.adl();r.emit(0xed,0x38,0xc7);r.ld(0x32,0xffe100)
    r.emit(0xed,0x00,0xc3,0xed,0x08,0xc5)
    r.out(0xc3,0x83);r.emit(0xed,0x10,0xc0)
    r.out(0xc0,0x77);r.out(0xc1,0x66);r.out(0xc3,3);r.out(0xc7,0xa5)
    r.emit(0x76)
    path=d/'uart-reset.bin';path.write_bytes(r.b);vm=VM(path)
    try:
        for iteration in range(2):
            vm.cmd('cont');vm.halted();got=regs(vm)
            assert got['BC']==0x0060 and got['DE']==0x0200,got
            f=d/'reset-memory.bin'
            vm.cmd('pmemsave',{'val':0xffe100,'size':1,'filename':str(f)})
            assert f.read_bytes()==b'\x00',f.read_bytes()
            if iteration==0:
                vm.cmd('stop');vm.cmd('system_reset')
    finally:
        vm.close()
    print('PASS: UART0 reset values restored after register writes')
