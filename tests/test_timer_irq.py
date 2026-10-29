#!/usr/bin/env python3
import pathlib,re,tempfile,time
from ez80_testlib import VM

class ROM:
 def __init__(self):self.b=bytearray([0x5b,0xc3,5,0,0]);self.fix=[];self.labels={}
 def emit(self,*bs):self.b.extend(bs)
 def ld(self,op,value):self.emit(op);self.b.extend(value.to_bytes(3,'little'))
 def out(self,port,value):self.emit(0x3e,value,0xed,0x39,port)
 def label(self,name):self.labels[name]=len(self.b)
 def addr(self,op,name):self.emit(op);self.fix.append((len(self.b),name,3));self.emit(0,0,0)
 def jr(self,op,name):self.emit(op);self.fix.append((len(self.b),name,1));self.emit(0)
 def finish(self):
  for at,name,size in self.fix:
   val=self.labels[name]-(at+1) if size==1 else self.labels[name]
   self.b[at:at+size]=(val&((1<<(8*size))-1)).to_bytes(size,'little')
  return self.b

def regs(v):return {k:int(x,16) for k,x in re.findall(r'([A-Z0-9]+)=([0-9a-f]+)',v.hmp('info registers'))}
def memory(v,d,addr,size):
 f=d/'mem.bin';v.cmd('pmemsave',{'val':addr,'size':size,'filename':str(f)});return f.read_bytes()
def setup(r,madl=True,ticks=3125,continuous=True,timer=0):
 r.ld(0x31,0xb90000)
 if madl:r.emit(0xed,0x7d)
 r.addr(0x21,'isr');r.ld(0x22,0x6b054+4*timer)
 r.ld(0x21,0x6b1);r.emit(0xed,0xc7,0xed,0x5e) # odd I bit discarded
 r.out(0x10,0x20<<timer);r.out(0x64+5*timer,ticks>>8);r.out(0x63+5*timer,ticks&255)
 r.out(0x61+5*timer,1);r.out(0x60+5*timer,0x8f if continuous else 0x83)

def wait_final(v,pc):
 end=time.monotonic()+5
 while time.monotonic()<end:
  state=regs(v)
  if state['HALTED'] and state['PC']==pc:return state
  time.sleep(.002)
 raise AssertionError(('no final HALT',state))

with tempfile.TemporaryDirectory(prefix='f91-timer-') as td:
 d=pathlib.Path(td)
 for timer,madl in [(0,False),(0,True),(1,False),(1,True)]:
  r=ROM();setup(r,madl,timer=timer)
  r.emit(0xfb);r.label('loop');r.emit(0x76);r.ld(0x3a,0x6b100)
  r.emit(0xfe,3);r.jr(0x20,'loop');r.emit(0xf3);r.out(0x60+5*timer,0);r.emit(0x76)
  final=len(r.b);r.label('isr');r.emit(0xed,0x38,0x62+5*timer)
  r.ld(0x3a,0x6b100);r.emit(0x3c);r.ld(0x32,0x6b100);r.emit(0xfb)
  if madl:r.emit(0x5b)
  r.emit(0xed,0x4d)
  p=d/f'periodic-{timer}-{madl}.bin';p.write_bytes(r.finish())
  v=VM(p,extra=('-icount','shift=0'),machine='ez80f91-freertos,ram-boot=on',loader='-kernel')
  try:
   v.cmd('cont');state=wait_final(v,final)
   assert memory(v,d,0x6b100,1)==b'\x03'
   assert state['SPL']==0xb90000 and state['IFF1']==0,state
   if madl:assert memory(v,d,0xb8fffc,1)==b'\x01'
  finally:v.close()
  print(f'PASS: periodic 1 kHz Timer{timer}, HALT wake, odd I alignment, RETI'+('.L' if madl else ''))

 # Pending IRQ must wait until the instruction after EI has completed.
 r=ROM();setup(r,True,ticks=1,continuous=False);r.emit(*([0]*200))
 r.emit(0xfb);r.ld(0x01,0x123456);r.emit(0xf3,0x76);final=len(r.b)
 r.label('isr');r.emit(0xed,0x43);r.b.extend((0x6b104).to_bytes(3,'little'))
 r.emit(0xed,0x38,0x62,0xfb,0x5b,0xed,0x4d)
 p=d/'ei-delay.bin';p.write_bytes(r.finish());v=VM(p,extra=('-icount','shift=0'),machine='ez80f91-freertos,ram-boot=on',loader='-kernel')
 try:
  v.cmd('cont');wait_final(v,final)
  assert memory(v,d,0x6b104,3)==b'\x56\x34\x12'
 finally:v.close()
 print('PASS: pending IRQ observes the one-instruction EI delay')

 # Mixed interrupt entered from Z80 pushes marker 0 and returns to MBASE code.
 r=ROM();setup(r,True,ticks=3125,continuous=False)
 short=bytes([0xfb,0x76,0xf3,0x3e,0,0xed,0x39,0x60,0x76])
 for i,b in enumerate(short):r.emit(0x3e,b);r.ld(0x32,0xffe000+i)
 r.emit(0x3e,0xff,0xed,0x6d,0x40,0xc3,0,0xe0)
 r.label('isr');r.emit(0xed,0x38,0x62,0xfb,0x5b,0xed,0x4d)
 p=d/'short-irq.bin';p.write_bytes(r.finish());v=VM(p,extra=('-icount','shift=0'),machine='ez80f91-freertos,ram-boot=on',loader='-kernel')
 try:
  v.cmd('cont');state=wait_final(v,0xffe009)
  assert state['ADL']==0 and state['SPL']==0xb90000,state
  assert memory(v,d,0xb8fffd,3)==b'\x00\x02\xe0'
 finally:v.close()
 print('PASS: Timer0 Z80-to-ADL ISR and RETI.L return with marker 0')

 # One-shot terminal count is sticky even with IRQs disabled, then clears on read.
 r=ROM();r.out(0x64,0);r.out(0x63,1);r.out(0x60,0x83)
 r.emit(*([0]*200));r.emit(0xed,0x00,0x62,0xed,0x08,0x62,0xed,0x10,0x60,0x76)
 final=len(r.b);p=d/'one-shot.bin';p.write_bytes(r.finish())
 v=VM(p,extra=('-icount','shift=0'))
 try:
  v.cmd('cont');state=wait_final(v,final)
  assert state['BC']==0x0100 and state['DE']==0x8000,state
 finally:v.close()
 print('PASS: single pass stops TIM_EN, EOC sticky and read-to-clear')

 # Low-byte reads latch high byte, even while the count crosses a byte boundary.
 r=ROM();r.out(0x64,1);r.out(0x63,1);r.out(0x60,0x83)
 r.emit(0xed,0x00,0x63,*([0]*500),0xed,0x08,0x64)
 r.out(0x60,0);r.emit(0x76);final=len(r.b)
 p=d/'latch.bin';p.write_bytes(r.finish());v=VM(p,extra=('-icount','shift=0'))
 try:
  v.cmd('cont');state=wait_final(v,final)
  assert state['BC']==0x0101,state
 finally:v.close()
 print('PASS: Timer0 high-byte latch is held across countdown changes')

 # Clock powerdown freezes the counter and resuming it preserves remaining count.
 r=ROM();r.out(0x64,0x12);r.out(0x63,0x34);r.out(0x60,0x8f)
 r.out(0xdc,1);r.emit(0xed,0x00,0x63,*([0]*1000),0xed,0x08,0x64)
 r.out(0xdc,0);r.emit(*([0]*1000));r.emit(0xed,0x10,0x63,0xed,0x18,0x64)
 r.out(0x60,0);r.emit(0x76);final=len(r.b)
 p=d/'gating.bin';p.write_bytes(r.finish());v=VM(p,extra=('-icount','shift=0'))
 try:
  v.cmd('cont');state=wait_final(v,final)
  assert state['BC']==0x3412,state
  after=((state['DE']&255)<<8) | ((state['DE']>>8)&255)
  assert 0<after<0x1234,state
 finally:v.close()
 print('PASS: Timer0 clock powerdown freezes and resumes countdown')

# A repeating I/O instruction must be interruptible between iterations.
with tempfile.TemporaryDirectory(prefix='f91-block-io-irq-') as td:
 d=pathlib.Path(td);r=ROM();setup(r,True,ticks=50,continuous=False)
 r.ld(0x01,0x10000);r.ld(0x11,0xa3);r.ld(0x21,0x6b200);r.emit(0xfb)
 r.label('block');r.emit(0xed,0xc2,0xf3,0x76)
 r.label('isr');r.emit(0xed,0x43);r.b.extend((0x6b104).to_bytes(3,'little'))
 r.out(0x60,0);r.emit(0x76);final=len(r.b)
 p=d/'block-irq.bin';p.write_bytes(r.finish())
 v=VM(p,extra=('-icount','shift=0'),machine='ez80f91-freertos,ram-boot=on',loader='-kernel')
 try:
  v.cmd('cont');state=wait_final(v,final)
  remaining=int.from_bytes(memory(v,d,0x6b104,3),'little')
  assert 0 < remaining < 0x10000,(remaining,state)
  assert memory(v,d,0xb8fffc,4)==b'\x01'+r.labels['block'].to_bytes(3,'little'),state
 finally:v.close()
 print('PASS: INIRX yields between iterations; Timer0 saves the repeat PC and a partial count')

# Unlike HALT, F91 SLEEP can only leave via a reset source (PS0192 p.45).
with tempfile.TemporaryDirectory(prefix='f91-sleep-irq-') as td:
 d=pathlib.Path(td);r=ROM();setup(r,True,ticks=50,continuous=False)
 r.emit(0xfb,0xed,0x76);sleep_pc=len(r.b);r.emit(0x3e,0x5a,0x76)
 r.label('isr');r.emit(0x3e,1);r.ld(0x32,0x6b104);r.emit(0x76)
 p=d/'sleep-irq.bin';p.write_bytes(r.finish())
 v=VM(p,extra=('-icount','shift=0'),machine='ez80f91-freertos,ram-boot=on',loader='-kernel')
 try:
  v.cmd('cont');v.halted();time.sleep(.03);state=regs(v)
  assert state['SLEEP']==1 and state['PC']==sleep_pc and state['IFF1']==1,state
  assert memory(v,d,0x6b104,1)==b'\0',state
  v.cmd('stop');v.cmd('system_reset');assert regs(v)['SLEEP']==0
 finally:v.close()
 print('PASS: pending Timer0 IRQ cannot wake F91 SLP; system reset clears sleep')

# CLK_PPD2 gates Timer1 independently of Timer0; simultaneous channels retain state.
with tempfile.TemporaryDirectory(prefix='f91-dual-timer-') as td:
 d=pathlib.Path(td);r=ROM()
 for base in (0x60,0x65):
  r.out(base+4,0x12);r.out(base+3,0x34);r.out(base,0x8f)
 r.out(0xdc,2)
 r.emit(0xed,0x00,0x68,*([0]*1000),0xed,0x08,0x69)
 r.emit(0xed,0x10,0x63,0xed,0x18,0x64)
 r.out(0x60,0);r.out(0x65,0);r.emit(0x76);final=len(r.b)
 p=d/'independent.bin';p.write_bytes(r.finish());v=VM(p,extra=('-icount','shift=0'))
 try:
  v.cmd('cont');state=wait_final(v,final)
  assert state['BC']==0x3412,state
  after=((state['DE']&255)<<8)|((state['DE']>>8)&255)
  assert 0<after<0x1234,state
 finally:v.close()
 print('PASS: Timer1 powerdown freezes its count while Timer0 keeps running')
