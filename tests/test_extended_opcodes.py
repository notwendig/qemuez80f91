#!/usr/bin/env python3
"""Execution checks for documented eZ80 byte/index, BCD, I/O and control opcodes.

Expected results follow UM0077 instruction semantics; every ROM is executed by
QEMU and checked through QMP, including exact bytes written to RAM.
"""
import pathlib
import re
import subprocess
import tempfile
from ez80_testlib import VM, binary

S,Z,H,P,N,C = 0x80,0x40,0x10,4,2,1

class ROM:
    def __init__(self, adl=True):
        self.b=bytearray()
        if adl: self.emit(0x5b,0xc3,5,0,0)
    def emit(self,*values): self.b.extend(values)
    def ld(self,op,value,size=3,prefix=()):
        self.emit(*prefix,op); self.b.extend(value.to_bytes(size,'little'))
    def af(self,a,f):
        self.ld(0x01,(a<<8)|f); self.emit(0xc5,0xf1)
    def out(self,port,value): self.emit(0x3e,value,0xed,0x39,port)
    def put(self,address,value):
        self.emit(0x3e,value); self.ld(0x32,address)
    def save_af(self):
        self.emit(0x77,0x23,0xf5,0xd1,0x7b,0x77,0x23)

count=0

def registers(vm):
    return {name:int(value,16) for name,value in re.findall(r'([A-Z0-9]+)=([0-9a-f]+)',vm.hmp('info registers'))}


def run(name,rom,expected=None,memory=(),board=False,extra=()):
    global count
    file=directory/(name+'.bin'); file.write_bytes(rom.b if isinstance(rom,ROM) else rom)
    vm=VM(file,extra=('-icount','shift=0',*extra),
          machine='ez80f91-freertos,ram-boot=on' if board else 'ez80f91-minimal',
          loader='-kernel' if board else '-bios')
    try:
        vm.cmd('cont'); vm.halted(); got=registers(vm)
        for key,value in (expected or {}).items(): assert got[key]==value,(name,key,hex(value),got)
        for address,data in memory:
            output=directory/'result.bin'
            vm.cmd('pmemsave',{'val':address,'size':len(data),'filename':str(output)})
            actual=output.read_bytes()
            if actual != data:
                mismatch=next((i for i,(a,b) in enumerate(zip(actual,data)) if a!=b),None)
                raise AssertionError((name,hex(address),mismatch,
                       actual[max(0,(mismatch or 0)-4):(mismatch or 0)+8].hex(),
                       data[max(0,(mismatch or 0)-4):(mismatch or 0)+8].hex()))
    finally: vm.close()
    count+=1
    return got


def bcd(value): return (value//10)*16+value%10

def parity(value): return P if value.bit_count()%2==0 else 0

with tempfile.TemporaryDirectory(prefix='ez80-extended-') as temporary:
    directory=pathlib.Path(temporary)
    # Exhaust all valid two-digit packed-BCD operand pairs, including carry.
    for opcode,sub,carry_in in [(0xc6,False,None),(0xd6,True,None),
                                (0xce,False,'both'),(0xde,True,'both')]:
        r=ROM();r.ld(0x31,0xbfff00);r.ld(0x21,0xb80000);expected=bytearray()
        for carry in ([0,1] if carry_in else [0]):
            for a in range(100):
                for b in range(100):
                    aa,bb=bcd(a),bcd(b)
                    r.emit(0x37 if carry else 0xb7,0x3e,aa,opcode,bb,0x27);r.save_af()
                    decimal=a-b-carry if sub else a+b+carry
                    adjusted=bcd(decimal%100)
                    raw=(aa-bb-carry if sub else aa+bb+carry)&255
                    flags=(adjusted&S)|(Z if adjusted==0 else 0)|parity(adjusted)
                    flags|=N if sub else 0
                    flags|=C if decimal<0 or decimal>99 else 0
                    flags|=(raw^adjusted)&H
                    expected.extend((adjusted,flags))
        r.emit(0x76)
        run(f'bcd-{opcode:02x}',r,{'HL':0xb80000+len(expected)},[(0xb80000,expected)],board=True)
    print('PASS: DAA after ADD/SUB/ADC/SBC, 60000 valid BCD operand/carry combinations')

    for old in (0,1,0xff,0x80,0x7f):
        r=ROM();r.ld(0x31,0xfffff0);r.af(old,0xff);r.emit(0xed,0x44,0x76)
        result=(-old)&255
        flags=(result&S)|(Z if not result else 0)|N|(H if old&15 else 0)|(P if old==128 else 0)|(C if old else 0)
        run(f'neg-{old}',r,{'AF':result<<8|flags})
    for carry in (0,1):
        r=ROM();r.ld(0x31,0xfffff0);r.af(0x5a,S|Z|P|H|N|carry);r.emit(0x3f,0x76)
        run(f'ccf-{carry}',r,{'AF':0x5a00|S|Z|P|(H if carry else C)})
    print('PASS: NEG and CCF boundary flags')

    # All documented register-only index-byte loads. Memory forms deliberately
    # use normal H/L and are tested separately below.
    initial={0:0x112233,1:0x445566,2:0x778899,3:0xaabbcc,4:0xddeeff,7:0x42}
    def read_byte(state,reg,index):
        if reg==7:return state[7]
        key=index if reg in (4,5) else reg//2
        return state[key]>>(8 if reg%2==0 else 0)&255
    for prefix,index in [(0xdd,3),(0xfd,4)]:
        for dst in (0,1,2,3,4,5,7):
            for src in (0,1,2,3,4,5,7):
                if dst not in (4,5) and src not in (4,5):continue
                state=dict(initial);value=read_byte(state,src,index)
                if dst==7:state[7]=value
                else:
                    key=index if dst in (4,5) else dst//2;shift=8 if dst%2==0 else 0
                    state[key]=(state[key]&~(255<<shift))|(value<<shift)
                r=ROM();r.ld(0x31,0xfffff0);r.af(initial[7],0x95)
                for op,key in [(1,0),(0x11,1),(0x21,2)]:r.ld(op,initial[key])
                r.ld(0x21,initial[3],prefix=(0xdd,));r.ld(0x21,initial[4],prefix=(0xfd,))
                r.emit(prefix,0x40+dst*8+src,0x76)
                run(f'index-ld-{prefix:02x}-{dst}-{src}',r,
                    dict(zip(('BC','DE','HL','IX','IY'),[state[i] for i in range(5)]))|{'AF':state[7]<<8|0x95})
        for register,op in [(4,0x26),(5,0x2e)]:
            r=ROM();r.ld(0x21,0xabcdef,prefix=(prefix,));r.emit(prefix,op,0x12,0x76)
            expected=0xab12ef if register==4 else 0xabcd12
            run(f'index-immediate-{prefix:02x}-{op:02x}',r,{'IX' if prefix==0xdd else 'IY':expected})
        vectors=[(0,0x7f,1,0,0x80,0x94),(1,0xff,0,1,0,0x51),
                 (2,0x80,1,0,0x7f,0x16),(3,0,0,1,0xff,0x93),
                 (4,0xf0,0x0f,0,0,0x54),(5,0xff,0xff,0,0,0x44),
                 (6,0x80,1,0,0x81,0x84),(7,0x80,1,0,0x80,0x16)]
        for operation,a,operand,carry,result,flags in vectors:
            for reg in (4,5):
                r=ROM();r.ld(0x31,0xfffff0);r.af(a,carry)
                value=0xab0000|(operand<<8|0x37 if reg==4 else 0x3700|operand)
                r.ld(0x21,value,prefix=(prefix,));r.emit(prefix,0x80+8*operation+reg,0x76)
                run(f'index-alu-{prefix:02x}-{operation}-{reg}',r,{'AF':result<<8|flags,'IX' if prefix==0xdd else 'IY':value})
        for op,old,result,flags in [(0x24,0x7f,0x80,0x95),(0x25,0x80,0x7f,0x17),
                                     (0x2c,0xff,0,0x51),(0x2d,0,0xff,0x93)]:
            high=op in (0x24,0x25)
            r=ROM();r.ld(0x31,0xfffff0);r.af(0,1)
            r.ld(0x21,0xab0000|(old<<8|0x55 if high else 0x5500|old),prefix=(prefix,))
            r.emit(prefix,op,0x76)
            run(f'index-incdec-{prefix:02x}-{op:02x}',r,
                {'AF':flags,'IX' if prefix==0xdd else 'IY':0xab0000|(result<<8|0x55 if high else 0x5500|result)})
        for op,old,result,flags in [(0x34,0x7f,0x80,0x95),(0x35,0x80,0x7f,0x17)]:
            r=ROM();r.ld(0x31,0xfffff0);r.put(0xfffffe,old);r.af(0x5a,1)
            r.ld(0x21,0xffffff,prefix=(prefix,));r.emit(prefix,op,0xff,0x76)
            run(f'index-memory-incdec-{prefix:02x}-{op:02x}',r,{'AF':0x5a00|flags},[(0xfffffe,bytes([result]))])
    print('PASS: IXH/IXL/IYH/IYL loads, ALU, INC/DEC and indexed-memory INC/DEC')
    # UM0077 map: ED31 loads IY; ED37 loads IX (not the other way around).
    for op,target in [(0x31,'IY'),(0x37,'IX')]:
        for short in (False,True):
            r=ROM();r.ld(0x31,0xfffff0)
            for i,v in enumerate([0x56,0x34,0x12]):r.put(0xffe080+i,v)
            r.emit(0x3e,0xff,0xed,0x6d);r.af(0x5a,0x95)
            r.ld(0x21,0xffe080);r.ld(0x21,0x111111,prefix=(0xdd,));r.ld(0x21,0x222222,prefix=(0xfd,))
            if short:r.emit(0x52)
            r.emit(0xed,op,0x76)
            expected={'IX':0x111111,'IY':0x222222,'HL':0xffe080,'AF':0x5a95}
            expected[target]=0x3456 if short else 0x123456
            run(f'ld-index-from-hl-{op:02x}-{short}',r,expected)
    print('PASS: corrected ED31/ED37 index-register destinations in both address widths')


    for op,expected_a,expected_mem in [(0x67,0x24,0x13),(0x6f,0x23,0x41)]:
        for suffix,addr in [((),0xffe080),((0x52,),0xffe080)]:
            r=ROM();r.ld(0x31,0xfffff0);r.put(addr,0x34);r.af(0x21,1)
            if suffix:r.emit(0x3e,0xff,0xed,0x6d,0x3e,0x21)
            r.ld(0x21,addr);r.emit(*suffix,0xed,op,0x76)
            run(f'rotate-decimal-{op:02x}-{len(suffix)}',r,
                {'AF':expected_a<<8|parity(expected_a)|C},[(addr,bytes([expected_mem]))])
    r=ROM();r.ld(0x31,0xfffff0);r.af(0xff,1);r.ld(0x01,0x8000)
    r.emit(0xed,0x04,0x76);run('tst-register',r,{'AF':0xff90,'BC':0x8000})
    r=ROM();r.emit(0x3e,0x80,0xed,0x64,0x7f,0x76);run('tst-immediate',r,{'AF':0x8054})
    r=ROM();r.put(0xffe000,0x81);r.ld(0x21,0xffe000);r.emit(0x3e,0xff,0xed,0x34,0x76)
    run('tst-memory',r,{'AF':0xff94},[(0xffe000,b'\x81')])
    print('PASS: RLD/RRD in long/short addressing and TST forms')

    # Refresh register low seven bits advance for each M1/prefix fetch; bit 7
    # remains fixed. LD R,A itself overwrites the post-fetch R value.
    r=ROM();r.ld(0x31,0xfffff0);r.af(0,1);r.emit(0xfb,0,0x3e,0xfe,0xed,0x4f,0xed,0x5f,0x76)
    run('ld-refresh-wrap',r,{'AF':0x8085,'R':0x81,'IFF1':1,'IFF2':1})
    for iv,expected_f in [(0,0x45),(0x8001,0x85)]:
        r=ROM();r.ld(0x31,0xfffff0);r.af(0,1);r.ld(0x21,iv);r.emit(0xed,0xc7,0xfb,0,0xed,0xd7,0x76)
        run(f'ld-hl-i-{iv}',r,{'HL':iv,'I':iv,'AF':expected_f})
    print('PASS: LD R,A / LD A,R refresh wrap and LD HL,I flags')

    # Port address checks use UART0's scratch register, plus the GPIO latches.
    for op,reg in [(0x40,0),(0x48,1),(0x50,2),(0x58,3),(0x60,4),(0x68,5),(0x78,7)]:
        r=ROM();r.ld(0x31,0xfffff0);r.out(0xc7,0x81);r.af(0x22,1);r.ld(0x01,0xc7)
        r.emit(0xed,op,0x76)
        expected={'AF':0x2285}
        if reg==7:expected['AF']=0x8185
        elif reg<2:expected['BC']=0x81c7 if reg==0 else 0x81
        elif reg<4:expected['DE']=0x8100 if reg==2 else 0x81
        else:expected['HL']=0x8100 if reg==4 else 0x81
        run(f'in-bc-{op:02x}',r,expected)
    for op,value in [(0x41,0),(0x49,0xc7),(0x51,0x81),(0x59,0x42),(0x61,0x24),(0x69,0x18),(0x79,0xa5)]:
        r=ROM();r.ld(0x31,0xfffff0);r.af(0xa5,0x95);r.ld(0x01,0xc7);r.ld(0x11,0x8142);r.ld(0x21,0x2418)
        r.emit(0xed,op,0xed,0x38,0xc7,0x76)
        run(f'out-bc-{op:02x}',r,{'AF':value<<8|parity(value)|(value&S)|C|(Z if value==0 else 0)})
    for a,expected in [(0,0x5a),(1,0xff)]:
        r=ROM();r.ld(0x31,0xfffff0);r.out(0xc7,0x5a);r.af(a,0x95);r.emit(0xdb,0xc7,0x76)
        run(f'in-immediate-{a}',r,{'AF':expected<<8|0x95})
    r=ROM();r.out(0xc7,0xaa);r.emit(0x3e,1,0xd3,0xc7,0xed,0x38,0xc7,0x76)
    run('out-immediate-high-byte',r,{'AF':0xaa84})
    r=ROM();r.out(0xc7,0xff);r.ld(0x01,0x12c7);r.emit(0xed,0x74,0x80,0x76)
    run('tstio-c-only',r,{'AF':0xff90,'BC':0x12c7})
    print('PASS: IN/OUT (BC), full A:n port addresses, unchanged IN(n) flags, TSTIO')

    for op in [0x82,0x83,0x8a,0x8b,0x92,0x93,0x9a,0x9b,
               0xa2,0xa3,0xaa,0xab,0xb2,0xb3,0xba,0xbb,
               0x84,0x8c,0xa4,0xac,0x94,0x9c,0xb4,0xbc,0xc2,0xc3,0xca,0xcb]:
        # An independent specification table classifies the instruction family.
        m_family=op in [0x82,0x83,0x8a,0x8b,0x92,0x93,0x9a,0x9b]
        io2=op in [0x84,0x8c,0xa4,0xac,0x94,0x9c,0xb4,0xbc]
        extended=op in [0x94,0x9c,0xb4,0xbc,0xc2,0xc3,0xca,0xcb]
        repeating=op in [0x92,0x93,0x9a,0x9b,0xb2,0xb3,0xba,0xbb,0x94,0x9c,0xb4,0xbc,0xc2,0xc3,0xca,0xcb]
        output=op in [0x83,0x8b,0x93,0x9b,0xa3,0xab,0xb3,0xbb,0xa4,0xac,0xb4,0xbc,0xc3,0xcb]
        down=op in [0x8a,0x8b,0x9a,0x9b,0xaa,0xab,0xba,0xbb,0x8c,0xac,0x9c,0xbc,0xca,0xcb]
        direction=-1 if down else 1
        iterations=3 if repeating else 1
        port=0xa5 if down else 0xa3
        hl=0xffe002 if down else 0xffe000
        bc=3 if extended else ((3 if repeating else 0)<<8)|port
        de=port if extended else 0x123456
        r=ROM();r.ld(0x31,0xfffff0)
        for address,value in [(0xa3,0x81),(0xa4,0x42),(0xa5,0x24)]:r.out(address,value)
        initial_data=[0x96,0x27,0x53] if output else [0x81,0x42,0x24]
        for i,v in enumerate(initial_data):r.put(0xffe000+i,v)
        r.af(0x5a,0x95);r.ld(0x01,bc);r.ld(0x11,de);r.ld(0x21,hl)
        r.emit(0xed,op)
        if output:
            r.emit(0xf5)
            for i,io in enumerate([0xa3,0xa4,0xa5]):
                r.emit(0xed,0x38,io);r.ld(0x32,0xffe010+i)
            r.emit(0xf1)
        r.emit(0x76)
        gpio={0xa3:0x81,0xa4:0x42,0xa5:0x24};data=bytearray(initial_data);last=0
        for _ in range(iterations):
            io=de&0xffff if extended else (bc&255 if m_family else bc&0xffff)
            if output:
                last=data[hl-0xffe000]
                if io in gpio:gpio[io]=last
            else:
                last= gpio.get(io,0xff);data[hl-0xffe000]=last
            hl+=direction
            if extended:
                bc-=1
                if io2:de+=direction
                remaining=bc
            else:
                b=((bc>>8)-1)&255;c=(bc+direction)&255 if m_family or io2 else bc&255
                bc=(bc&0xff0000)|(b<<8)|c;remaining=b
        flags=(0x95 if remaining else 0xd5)|(N if last&128 else 0)
        checks=[(0xffe000,bytes(data))]
        if output:checks.append((0xffe010,bytes(gpio[io] for io in [0xa3,0xa4,0xa5])))
        run(f'block-io-{op:02x}',r,{'BC':bc,'DE':de,'HL':hl,'AF':0x5a00|flags},checks)
    print('PASS: all 28 block-I/O encodings (classic, M, 2, 2R and RX), flags and pointer/count updates')

    # All eight restart vectors use a real call/return stack frame in both modes.
    for adl in (False,True):
        for vector in range(0,0x40,8):
            r=ROM(adl=False);r.emit(0xc3,0x80,0)
            r.b.extend(bytes(0x80-len(r.b)))
            if adl:r.emit(0x5b,0xc3,0x85,0,0)
            r.ld(0x31,0xfffff0 if adl else 0xfff0,size=3 if adl else 2)
            r.emit(0xc7+vector,0x76)
            handler=bytes([0x3e,vector,0xc9]);r.b[vector:vector+len(handler)]=handler
            # Vector zero overlaps the reset bootstrap; test it below with
            # a RAM-debug image that patches address zero after bootstrapping.
            if vector==0:continue
            run(f'rst-{adl}-{vector}',r,{'AF':vector<<8,'SPL' if adl else 'SPS':0xfffff0 if adl else 0xfff0},board=True)
    # RST 0 bootstraps once with a forward jump, then patches vector 0 in RAM
    # (RAM debug profile), so the restart can exercise address zero genuinely.
    r=ROM();r.ld(0x31,0xbfff00)
    for address,value in enumerate([0x3e,0x42,0xc9]):r.put(address,value)
    r.emit(0xc7,0x76);run('rst-zero',r,{'AF':0x4200,'SPL':0xbfff00},board=True)
    r=ROM(adl=False);r.emit(0xc3,0,1);r.b.extend(bytes(0x100-len(r.b)));r.ld(0x31,0xfff0,size=2)
    for address,value in enumerate([0x3e,0x42,0xc9]):
        r.emit(0x3e,value);r.ld(0x32,address,size=2)
    r.emit(0xc7,0x76);run('rst-zero-z80',r,{'AF':0x4200,'SPS':0xfff0,'ADL':0},board=True)

    r=ROM();r.ld(0x31,0xfffff0);r.ld(0x01,0x1234);r.emit(0xc5,0xed,0x45)
    r.b.extend(bytes(0x1234-len(r.b)));r.emit(0x76)
    run('retn-adl',r,{'PC':0x1235,'SPL':0xfffff0})
    r=ROM(adl=False);r.ld(0x31,0xfff0,size=2);r.ld(0x01,0x1234,size=2);r.emit(0xc5,0xed,0x45)
    r.b.extend(bytes(0x1234-len(r.b)));r.emit(0x76)
    run('retn-z80',r,{'PC':0x1235,'SPS':0xfff0,'ADL':0},board=True)

    # RST.SIL from ADL pushes a short return on SPS and the mode/high byte
    # on SPL; RET.LIS in the banked handler must recover the original PC.
    r=ROM();r.b[:]=bytes([0x5b,0xc3,0,1,0])+bytes(0x100-5)
    r.ld(0x31,0xbfff00);r.ld(0x31,0xfff0,size=2,prefix=(0x40,))
    r.emit(0x3e,0xb8,0xed,0x6d,0xed,0x7d)
    for i,v in enumerate([0x3e,0x42,0x49,0xc9]):r.put(0xb80028+i,v)
    r.af(0x11,0x95);r.emit(0x52,0xef);resume=len(r.b);r.emit(0x76)
    run('rst-sil-mixed',r,{'AF':0x4295,'ADL':1,'SPS':0xfff0,'SPL':0xbfff00},
        [(0xb8ffee,resume.to_bytes(2,'little')),(0xbffefe,bytes([3,resume>>16]))],board=True)
    # The reverse transition uses the long stack only and returns to MBASE.
    r=ROM();r.b[:]=bytes([0x5b,0xc3,0,1,0])+bytes(0x100-5)
    r.b[0x28:0x2c]=bytes([0x3e,0x42,0x5b,0xc9])
    r.ld(0x31,0xbfff00);r.ld(0x31,0xfff0,size=2,prefix=(0x40,))
    r.emit(0x3e,0xb8,0xed,0x6d,0xed,0x7d)
    for i,v in enumerate([0x49,0xef,0x76]):r.put(0xb8e000+i,v)
    r.af(0x11,0x95);r.emit(0x40,0xc3,0,0xe0)
    run('rst-lis-mixed',r,{'AF':0x4295,'ADL':0,'PC':0xb8e003,'SPS':0xfff0,'SPL':0xbfff00},
        [(0xbffefd,bytes([2,2,0xe0]))],board=True)
    for mode,target in [(1,0x80),(0,0xffe000)]:
        r=ROM();r.emit(0xed,0x7d,0x3e,0xff,0xed,0x6d)
        stack=0xfffff0-(4 if mode else 3)
        frame=bytes([2 | mode])+target.to_bytes(3,'little')[:3 if mode else 2]
        for i,v in enumerate(frame):r.put(stack+i,v)
        if not mode:r.put(target,0x76)
        r.ld(0x31,stack);r.emit(0x5b,0xed,0x45)
        if mode:
            assert len(r.b)<target;r.b.extend(bytes(target-len(r.b)));r.emit(0x76)
        run(f'retn-long-frame-{mode}',r,{'ADL':mode,'PC':target+1,'SPL':0xfffff0})
    print('PASS: restart vectors, mixed SPS/SPL frames and RETN including F91 markers')

    # Size prefixes select both the extended count width and the memory bank.
    r=ROM();r.ld(0x31,0xfffff0);r.out(0xa3,0x81);r.put(0xffffff,0x5a)
    r.emit(0x3e,0xff,0xed,0x6d);r.af(0x5a,0x95)
    r.ld(0x01,0x010001);r.ld(0x11,0x3400a3);r.ld(0x21,0x12fffe)
    r.emit(0x52,0xed,0xc2,0x76)
    run('block-io-short-width',r,{'BC':0,'DE':0x3400a3,'HL':0xffff,'AF':0x5ad7},
        [(0xfffffe,bytes([0x81,0x5a]))])
    r=ROM();r.ld(0x31,0xfffff0);r.out(0xa3,0x81);r.af(0x5a,0x95)
    r.ld(0x01,0x1200a3);r.ld(0x21,0xffe000);r.emit(0xed,0xb2,0x76)
    run('block-io-b-zero-wrap',r,{'BC':0x1200a3,'HL':0xffe100,'AF':0x5ad7},
        [(0xffe000,b'\x81'+b'\xff'*255)])
    r=ROM();r.ld(0x31,0xbfff00);r.out(0xa3,0x81);r.af(0x5a,0x95)
    r.ld(0x01,0x10001);r.ld(0x11,0xa3);r.ld(0x21,0xb80000);r.emit(0xed,0xc2,0x76)
    run('block-io-24bit-count',r,{'BC':0,'DE':0xa3,'HL':0xb90001,'AF':0x5ad7},
        [(0xb80000,b'\x81'*0x10001)],board=True)
    # New opcodes use the shared runtime decoder across 16/24-bit boundaries.
    r=ROM();r.ld(0x31,0xbfff00)
    for address,v in [(0xb8ffff,0xed),(0xb80000,0x44),(0xb80001,0x76)]:r.put(address,v)
    r.emit(0x3e,0xb8,0xed,0x6d,0x3e,0x80,0x40,0xc3,0xff,0xff)
    run('new-opcode-z80-fetch-wrap',r,{'ADL':0,'PC':0xb80002,'AF':0x8087},board=True)
    r=ROM();r.ld(0x21,0xabcdef,prefix=(0xdd,))
    for address,v in [(0xfffffe,0xdd),(0xffffff,0x26),(0,0x12),(1,0x76)]:r.put(address,v)
    r.ld(0xc3,0xfffffe)
    run('new-opcode-adl-fetch-wrap',r,{'PC':2,'IX':0xab12ef},board=True)
    print('PASS: block-I/O count/address widths, B=0 wrap and instruction fetch boundaries')

    r=ROM();r.emit(0xed,0x76,0x3e,0x5a,0x76)
    file=directory/'sleep.bin';file.write_bytes(r.b)
    vm=VM(file)
    try:
        vm.cmd('cont');vm.halted();got=registers(vm)
        assert got['SLEEP']==1 and got['PC']==7 and got['AF']==0,got
        vm.cmd('stop');vm.cmd('system_reset');assert registers(vm)['SLEEP']==0
    finally:vm.close()
    count+=1
    print('PASS: SLP stops the CPU and reset clears sleep state')
    # Reserved instruction encodings and hardware TRAP frames are covered by
    # test_illegal_traps.py (including Z80/ADL and mixed modes).
    print(f'PASS: {count} ROM-level execution scenarios')
