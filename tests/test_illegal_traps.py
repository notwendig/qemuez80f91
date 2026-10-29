#!/usr/bin/env python3
"""Illegal instructions trap at vector zero with the illegal-byte PC and mixed frame."""
from pathlib import Path
import re
import sys
import tempfile
from ez80_testlib import VM
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/zds'))
from rsp import RSP

RESERVED=[bytes([0xed,op]) for op in (0xd2,0xd3,0xda,0xdb,0xff)]+[
    bytes([0xdd,0x76]),bytes([0xfd,0x76]),bytes([0xcb,0x30]),
    bytes([0xdd,0xcb,0,0x36]),bytes([0xfd,0xcb,0,0x30]),
    bytes([0x52,0xdd,0x84]),bytes([0x52,0xed,0x76]),bytes([0x40,0xed,0x45])]

def check(code,adl,madl,boundary=False,offset=None):
    with tempfile.TemporaryDirectory(prefix='ez80-trap-') as td:
        root=Path(td);rom=root/'halt.bin';rom.write_bytes(b'\x76');path=root/'gdb.sock'
        vm=VM(rom,extra=('-nic','none','-gdb',f'unix:{path},server=on,wait=off'))
        g=RSP(unix=str(path))
        try:
            for port,value in ((0xf8,0x60),(0xaa,0),(0xab,0),(0xac,7),(0xad,0x28)):
                g.write_memory(0x1000000+port,bytes([value]))
            base=0 if adl else 0x10000
            pc=base+(offset if offset is not None else 0xfff if boundary else 0x100)
            g.write_memory(base,b'\x76');g.write_memory(0,b'\x76')
            if not adl and (pc & 65535)+len(code)>65536:
                for i,b in enumerate(code):g.write_memory(base+((pc+i)&65535),bytes([b]))
            else:g.write_memory(pc,code)
            regs=g.registers();regs[0]=pc;regs[9]=0x50000;regs[10]=0x8000
            regs[17]=base>>16;regs[18]=adl;regs[19]=madl;regs[20]=regs[21]=1
            g.set_registers(regs)
            pc = ((pc+len(code)-1)&0xffffff) if adl else base+((pc+len(code)-1)&65535)
            vm.cmd('cont');vm.halted();vm.cmd('stop')
            result={k:int(v,16) for k,v in re.findall(r'([A-Z0-9]+)=([0-9a-f]+)',vm.hmp('info registers'))}
            assert result['PC']==(1 if adl or madl else base+1) and result['ADL']==(adl or madl) and result['MADL']==madl,result
            assert result['IFF1']==1 and result['IFF2']==1,result
            if adl:
                at=0x50000-3-madl
                expected=(b'\x03' if madl else b'')+pc.to_bytes(3,'little')
                assert g.memory(at,len(expected))==expected,(code,result)
                assert result['SPL']==at and result['SPS']==0x8000,result
            elif madl:
                assert g.memory(0x4fffd,3)==b'\x02'+(pc&65535).to_bytes(2,'little'),result
                assert result['SPL']==0x4fffd and result['SPS']==0x8000,result
            else:
                assert g.memory(base+0x7ffe,2)==(pc&65535).to_bytes(2,'little'),result
                assert result['SPS']==0x7ffe and result['SPL']==0x50000-madl,result
                if madl:assert g.memory(0x4ffff,1)==b'\x02'
        finally:g.socket.close();vm.close()

for adl in (0,1):
    for madl in (0,1):
        for code in RESERVED:check(code,adl,madl)
        print(f'PASS: reserved-opcode TRAP, illegal-byte PC, stacks and IFF; ADL={adl} MADL={madl}')
check(bytes.fromhex('cb30'),1,1,True)
print('PASS: illegal opcode crossing a translation-page boundary')

# Supervisor skips CB30, then RET.L restores short mode and the caller stack.
with tempfile.TemporaryDirectory(prefix='ez80-trap-return-') as td:
    root=Path(td);rom=root/'halt.bin';rom.write_bytes(b'\x76');path=root/'gdb.sock'
    vm=VM(rom,extra=('-nic','none','-gdb',f'unix:{path},server=on,wait=off'))
    g=RSP(unix=str(path))
    try:
        for port,value in ((0xf8,0x60),(0xaa,0),(0xab,0),(0xac,7),(0xad,0x28)):
            g.write_memory(0x1000000+port,bytes([value]))
        # LD HL,1; ADD HL,SP; INC (HL); RET.L
        g.write_memory(0,bytes.fromhex('21010000393449c9'))
        g.write_memory(0x10100,bytes.fromhex('cb3076'))
        regs=g.registers();regs[0]=0x10100;regs[9]=0x50000;regs[10]=0x8000
        regs[17]=1;regs[18]=0;regs[19]=1;regs[20]=regs[21]=1;g.set_registers(regs)
        vm.cmd('cont');vm.halted();vm.cmd('stop')
        result={k:int(v,16) for k,v in re.findall(r'([A-Z0-9]+)=([0-9a-f]+)',vm.hmp('info registers'))}
        assert result['PC']==0x10103 and result['ADL']==0,result
        assert result['SPL']==0x50000 and result['SPS']==0x8000,result
        print('PASS: CP/M-style mixed supervisor TRAP and RET.L to Z80 caller')
    finally:g.socket.close();vm.close()

check(bytes.fromhex("cb30"),0,1,offset=0xffff)
print("PASS: illegal opcode PC preserves MBASE across 16-bit fetch wrap")
