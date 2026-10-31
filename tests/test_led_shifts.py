#!/usr/bin/env python3
"""Assemble the real LED shifter with ZDS and check its RAM results in QEMU."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from ez80_testlib import VM

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from ihex_to_bin import convert
work=ROOT/'build/led-shift-probe';work.mkdir(parents=True,exist_ok=True)
zds=Path.home()/'.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5'
source=ROOT/'subprojects/FreeRTOS-eZ80f91/EZ80F910300ZCOG/src/ez80_letsS.asm'
shutil.copyfile(source,work/'shift.asm')
initial=bytes.fromhex('12813462564378249a05bce6dec7f0a8')
lines=['XREF _shiftDisplay','XDEF _dir','XDEF _dply','XDEF _set_vector',
       '_dir EQU 0FFE080h','_dply EQU 0FFE100h',
       'DEFINE .RESET,SPACE=ROM,ORG=0','SEGMENT .RESET',
       'DB 05Bh,0C3h,5,0,0','.ASSUME ADL=1','DI','STMIX','LD SP,0FFFF00h',
       'XOR A','OUT0 (0AAh),A']
def store(address,value):lines.extend([f'LD A,{value}',f'LD ({address}),A'])
for direction in range(5):
    store(0xffe080,direction)
    for i,value in enumerate(initial):store(0xffe100+i,value)
    for address,value in ((0xffe0fe,0x5a),(0xffe0ff,0xa5),(0xffe110,0xa5),(0xffe111,0x5a)):
        store(address,value)
    lines.extend(['CALL _shiftDisplay','LD HL,_dply',f'LD DE,{0xffe200+direction*16}',
                  'LD BC,16','LDIR'])
lines.extend(['HALT','_set_vector: RET','END'])
(work/'boot.asm').write_text('\n'.join(lines)+'\n')
(work/'probe.linkcmd').write_text('''-FORMAT=INTEL32
-map -maxhexlen=64 -quiet -warnoverlap -xref -unresolved=fatal
RANGE ROM $000000 : $03FFFF
RANGE RAM $FFE000 : $FFFFFF
RANGE EXTIO $000000 : $00FFFF
RANGE INTIO $000000 : $0000FF
ORDER .RESET,CODE,TEXT
"probe" = "boot.obj", "shift.obj"
''')
env=dict(os.environ,WINEDEBUG='-all',WINEPREFIX=str(Path.home()/'.wine'))
for filename in ('boot.asm','shift.asm'):
    subprocess.run(['wine',str(zds/'bin/ez80asm.exe'),'-cpu:eZ80F91',
                    '-include:Z:'+str(zds/'include/zilog').replace('/','\\'),filename],
                   cwd=work,env=env,check=True)
subprocess.run(['wine',str(zds/'bin/eZ80link.exe'),'@probe.linkcmd'],cwd=work,env=env,check=True)
convert(work/'probe.hex',work/'probe.bin',0x40000)
expected=[]
none=bytearray(initial)
for row in range(7):none[row*2]=initial[row*2+1]
expected.append(bytes(none))
left=bytearray(initial)
for row in range(7):
    low,high=initial[row*2:row*2+2]
    left[row*2:row*2+2]=bytes([((low<<1)|(high>>7))&255,((high<<1)|1)&255])
expected.append(bytes(left))
expected.append(initial[2:]+bytes([initial[1],255]))
right=bytearray(initial)
for row in range(7):
    low,high=initial[row*2:row*2+2]
    right[row*2:row*2+2]=bytes([(low>>1)|((high&1)<<7),(high>>1)|128])
expected.append(bytes(right))
expected.append(bytes([initial[15],255])+initial[:14])
vm=VM(work/'probe.bin',extra=('-nic','none'))
try:
    vm.cmd('cont');vm.halted();vm.cmd('stop')
    output=work/'result.bin'
    vm.cmd('pmemsave',dict(val=0xffe200,size=80,filename=str(output)))
    actual=output.read_bytes()
    assert actual==b''.join(expected),(actual.hex(),b''.join(expected).hex())
finally:vm.close()
print('PASS: actual ZDS LED shifter in QEMU, all five directions; independent row carry; vertical shifts avoid out-of-bounds source rows')
