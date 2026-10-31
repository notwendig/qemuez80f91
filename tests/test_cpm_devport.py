#!/usr/bin/env python3
"""Select independent raw drives and high banks, preserving LEDs and files."""
import json
from pathlib import Path
import tempfile
import time
from ez80_testlib import VM

with tempfile.TemporaryDirectory(prefix='cpm-devport-') as temp:
    root = Path(temp)
    disks = root / 'disk directory';disks.mkdir()
    originals = {}
    paths = {}
    for drive in (0, 1, 2, 3, 8, 9):
        size = 256256 if drive < 4 else 4194304
        data = bytearray(b'\xe5' * size);data[0] = drive;data[-1] = drive + 0x40
        path = disks / (chr(65 + drive) + ('.img' if drive else ''))
        path.write_bytes(data);originals[drive] = data;paths[drive] = path
    rom = bytearray([0x5b,0xc3,5,0,0])
    def ld(op, addr):rom.extend([op,*addr.to_bytes(3,'little')])
    def out(port,value):rom.extend([0x3e,value,0xed,0x39,port])
    def sample(addr,slot):ld(0x3a,addr);ld(0x32,0xffe100+slot)
    def select(value,slot):
        ld(0x01,0x1234);rom.extend([0x3e,value,0xed,0x79,0xed,0x78])
        ld(0x32,0xffe100+slot)
    out(0xaa,0);out(0xae,0x80);out(0xaf,0xbf);out(0xb0,0x28)
    out(0xb3,0);out(0xb1,0xd0);out(0xb2,0xff);out(0xb3,8)
    sample(0xf00004,0);sample(0xf00005,1)
    slot = 2
    for drive,data in originals.items():
        select(drive,slot);sample(0xd00000,slot+1)
        offset = len(data)-1
        selection = drive | ((offset >> 21) << 4)
        select(selection,slot+2)
        at = 0xd00000 + (offset & 0x1fffff)
        sample(at,slot+3)
        rom.extend([0x3e,drive+0x80]);ld(0x32,at)
        slot += 4
    # Missing E: and an out-of-file bank must neither resize nor create files.
    select(4,slot);sample(0xd00000,slot+1)
    select(0xf8,slot+2);sample(0xd00000,slot+3)
    rom.extend([0x3e,0xaa]);ld(0x32,0xd00000)
    rom.extend([0x3e,0x7f]);ld(0x32,0x800000)
    rom.extend([0x3e,0]);ld(0x32,0x800001)
    rom.append(0x76)
    firmware=root/'test.bin';firmware.write_bytes(rom)
    state=root/'kit.json'
    for attempt in range(2):
        vm=VM(firmware,machine='ez80f91-minimal',extra=(
            '-nic','none','-global',f'ez80f91-memory.dev-dir={disks}',
            '-global','ez80f91-memory.devport=0x1234',
            '-global',f'ez80f91-memory.kit-led-state={state}'))
        try:
            vm.cmd('cont');vm.halted();vm.cmd('stop')
            path=root/'samples';vm.cmd('pmemsave',dict(val=0xffe100,size=slot+4,filename=str(path)))
            expected=[0x34,0x12]
            for drive,data in originals.items():
                offset=len(data)-1;selection=drive|((offset>>21)<<4)
                expected.extend([drive,drive,selection,drive+(0x80 if attempt else 0x40)])
            expected.extend([0xff,0xff,0xf8,0xff])
            assert path.read_bytes()==bytes(expected),(path.read_bytes(),expected)
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                data=json.loads(state.read_text())
                if data['enabled'] and data['anode']==127 and data['cathode']==0:break
                time.sleep(.02)
            else:raise AssertionError(data)
        finally:vm.close()
        for drive,data in originals.items():
            expected=data.copy();expected[-1]=drive+0x80
            assert paths[drive].read_bytes()==expected,drive
        assert not (disks/'E.img').exists()
    print('PASS: configurable 16-bit port; six separate images; high-bank writes; restart persistence; missing drives; LEDs')
