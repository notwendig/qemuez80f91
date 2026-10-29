#!/usr/bin/env python3
import pathlib,re,tempfile
from ez80_testlib import VM

class Image:
    def __init__(self):self.b=bytearray([0x5b,0xc3,5,0,0])
    def emit(self,*x):self.b.extend(x)
    def ld(self,op,value):self.emit(op);self.b.extend(value.to_bytes(3,'little'))
    def out(self,port,value):self.emit(0x3e,value,0xed,0x39,port)
    def store(self,addr,value):self.emit(0x3e,value);self.ld(0x32,addr)

def registers(vm):
 return {k:int(v,16) for k,v in re.findall(r'([A-Z0-9]+)=([0-9a-f]+)',vm.hmp('info registers'))}

def run(d,name,img,expected,evb=False):
 path=d/(name+'.bin');path.write_bytes(img.b)
 flashdir=d/name;flashdir.mkdir()
 v=VM(path,machine='ez80f91-freertos,ram-boot=on' if evb else 'ez80f91-minimal',loader='-kernel' if evb else '-bios',cwd=flashdir)
 try:
  v.cmd('cont');v.halted();got=registers(v)
  for k,value in expected.items():assert got[k]==value,(name,k,got)
 finally:v.close()
 print('PASS:',name)

with tempfile.TemporaryDirectory(prefix='f91-memory-') as td:
 d=pathlib.Path(td)
 r=Image();r.store(0xffe100,0x5a);r.out(0xb5,0xb7)
 r.ld(0x3a,0xb7e100);r.emit(0x47) # B=A
 r.out(0xb4,0x7f);r.emit(0xed,0x10,0xb4) # D=masked RAM_CTL=40
 r.out(0xb4,0xc0);r.out(0xb5,0xff);r.emit(0xed,0x08,0xb5,0x76)
 run(d,'ram-remap-enable-and-register-masks',r,{'BC':0x5aff,'DE':0x4000})

 # Relocate Flash while executing from internal RAM, then jump into relocated ROM.
 r=Image()
 stub=bytes([0x3e,0x07,0xed,0x39,0xf7,0xc3,0x00,0x01,0x04])
 for i,b in enumerate(stub):r.store(0xffe000+i,b)
 r.ld(0xc3,0xffe000);r.b.extend(b'\xff'*(0x100-len(r.b)))
 r.emit(0xed,0x00,0xf7,0x76)
 run(d,'flash-remap-and-alignment-mask',r,{'ADL':1,'BC':0x0400,'PC':0x40104})

 # Internal RAM overrides Flash, and disabling it reveals the Flash below.
 r=Image();r.store(0xffe123,0xa5);r.out(0xb5,0)
 r.ld(0x3a,0xe123);r.emit(0x47);r.out(0xb4,0x40)
 r.ld(0x3a,0xe123);r.emit(0x4f);r.out(0xb4,0xc0)
 r.ld(0x3a,0xe123);r.emit(0x57,0x76)
 r.b.extend(b'\xff'*(0xe123-len(r.b)));r.emit(0x3c)
 run(d,'ram-over-flash-priority-and-disable',r,{'BC':0xa53c,'DE':0xa500})

 # Debug-RAM profile loads more than 256 KiB, and uses both external banks.
 r=Image();r.ld(0x31,0xb90000);r.ld(0x01,0x123456)
 r.emit(0xc5,0xd1);r.store(0x6b000,0x5a);r.ld(0x3a,0x6b000);r.emit(0x47)
 r.store(0xb90010,0xa5);r.ld(0x3a,0xb90010);r.emit(0x4f)
 r.emit(0xed,0x20,0xf8,0x76) # H=Flash disabled 60
 r.b.extend(b'\xff'*(0x45000-len(r.b)))
 run(d,'freertos-debug-ram-profile',r,{'BC':0x125aa5,'DE':0x123456,
     'HL':0x6000,'SPL':0xb90000},evb=True)

 # External SRAM contents survive decoder disable and re-enable on CS2.
 r=Image();r.store(0xb90000,0x42);r.out(0xb0,0)
 r.out(0xb0,0x28);r.ld(0x3a,0xb90000);r.emit(0x47)
 r.out(0xae,0xb8);r.ld(0x3a,0xb90000);r.emit(0x4f)
 r.out(0xae,0x80);r.ld(0x3a,0xb90000);r.emit(0x57,0x76)
 run(d,'cs2-disable-reenable-and-bank-relocation',r,{'BC':0x4200,'DE':0x4200},evb=True)

 # SRAM and internal Flash at the same address: disabling Flash reveals SRAM.
 r=Image();r.store(0xffe000,0x76)
 # Jump into RAM before remapping Flash over external data.
 stub=Image();stub.b=bytearray()
 stub.out(0xf7,4);stub.out(0xf8,0x88);stub.ld(0x3a,0x40000)
 stub.emit(0x47);stub.out(0xf8,0x60);stub.ld(0x3a,0x40000)
 stub.emit(0x4f,0x76)
 for i,b in enumerate(stub.b):r.store(0xffe000+i,b)
 r.store(0x40000,0x5a);r.ld(0xc3,0xffe000)
 run(d,'flash-over-external-sram-priority',r,{'BC':0xff5a},evb=True)
