#!/usr/bin/env python3
"""WD2797A command/data handshake, raw disk persistence and board extensions."""
import binascii
import json
from pathlib import Path
import sys
import tempfile
import time
from ez80_testlib import VM
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/zds'))
from rsp import RSP

with tempfile.TemporaryDirectory(prefix='wd2797a-') as temp:
    root=Path(temp);disks=root/'disk directory';disks.mkdir()
    paths={};original={};expected={}
    for drive in (0,1,2,3,8,9):
        size=256256 if drive<4 else 4194304
        data=bytearray(b'\xe5'*size);data[-1]=0x40+drive
        path=disks/(chr(65+drive)+('.img' if drive else ''))
        path.write_bytes(data);paths[drive]=path;original[drive]=bytes(data)
        expected[drive]=bytearray(data)
    paths[1].chmod(0o444)
    rom=root/'halt.bin';rom.write_bytes(b'\x76')
    base=0x1234
    def start():
        gdb=root/'gdb.sock';gdb.unlink(missing_ok=True)
        state=root/'kit.json'
        vm=VM(rom,machine='ez80f91-minimal,cs3=none',extra=(
            '-nic','none','-gdb',f'unix:{gdb},server=on,wait=off',
            '-global',f'ez80f91-memory.wd2797a={base}',
            '-global',f'ez80f91-memory.dev-dir={disks}',
            '-global',f'ez80f91-memory.kit-led-state={state}'))
        return vm,RSP(unix=str(gdb)),state
    vm,g,state=start()
    def rd(reg):return g.memory(0x1000000+base+reg,1)[0]
    def wr(reg,value):g.write_memory(0x1000000+base+reg,bytes([value]))
    def seek(drive,track,sector):
        wr(4,drive);wr(6,track>>8);wr(3,track&255);wr(0,0x10)
        assert not rd(0)&0x99
        wr(2,sector)
    def read_sector():
        wr(0,0x80);assert rd(0)&3==3
        data=bytes(rd(3) for _ in range(128))
        assert rd(5)&3==2
        assert not rd(0)&0xdd
        assert not rd(5)&2
        return data
    try:
        cfg=g.memory(0x100ff00,8)
        assert cfg==b'WD97'+base.to_bytes(2,'little')+b'\x01\x01',cfg
        g.write_memory(0x10000aa,b'\x00')
        assert g.memory(0x10000b3,1)==b'\x00'
        try:g.memory(0xd00000,1)
        except RuntimeError as error:assert 'unmapped memory' in str(error)
        else:raise AssertionError('Unexpected disk memory mapping')
        for drive in paths:
            track=76 if drive<4 else 1023;sector=26 if drive<4 else 32
            seek(drive,track,sector)
            assert read_sector()==original[drive][-128:]
            pattern=bytes((i+drive)&255 for i in range(128))
            wr(0,0xa0)
            if drive==1:
                assert rd(0)&0x40 and not rd(5)&1
                continue
            assert rd(0)&3==3
            for value in pattern:wr(3,value)
            assert not rd(0)&0xdd
            expected[drive][-128:]=pattern
            assert read_sector()==pattern
            wr(0,0xa0)
            for _ in range(17):wr(3,0xaa)
            wr(0,0xd8);assert rd(5)&2
            assert not rd(0)&1 and not rd(5)&2
            assert read_sector()==pattern  # Partial write was discarded.
        seek(0,0,1);wr(0,0x00);assert rd(0)&4
        wr(0,0x50);assert rd(1)==1
        wr(0,0x70);assert rd(1)==0
        wr(2,1);wr(0,0xc0)
        address=bytes(rd(3) for _ in range(6))
        crc=binascii.crc_hqx(b'\xfe\0\0\x01\0',0xffff)
        assert address==b'\0\0\x01\0'+crc.to_bytes(2,'big'),address
        assert rd(2)==0  # Read Address copies the ID track into Sector.
        seek(0,0,25);wr(0,0x90)
        assert bytes(rd(3) for _ in range(256))==b'\xe5'*256
        assert rd(0)&0x10 and not rd(5)&1  # End-of-track record not found.
        seek(0,1,25);wr(0,0xb0)
        multi=b'\x19'*128+b'\x1a'*128
        for byte in multi:wr(3,byte)
        assert rd(0)&0x10 and not rd(5)&1
        expected[0][(26+24)*128:(26+26)*128]=multi
        seek(0,1,25);assert read_sector()==multi[:128]
        wr(2,26);assert read_sector()==multi[128:]
        seek(0,0,1);wr(1,1);wr(0,0x80);assert rd(0)&0x10
        seek(0,0,27);wr(0,0x80);assert rd(0)&0x10
        wr(4,0x10);wr(0,0x80);assert rd(0)&0x10  # Absent second side.
        wr(4,4);wr(0,0x80);assert rd(0)&0x80     # Missing E:.
        wr(0,0xd1);wr(4,0);assert rd(5)&2      # Not-ready -> ready.
        rd(0);assert not rd(5)&2
        wr(0,0xd2);wr(4,4);assert rd(5)&2      # Ready -> not-ready.
        rd(0);wr(0,0xd0);assert not rd(5)&2
        seek(0,0,1);wr(0,0xa0);wr(3,0x42)
        vm.cmd('system_reset')
        assert rd(4)==0 and not rd(0)&1
        seek(0,0,1);assert read_sector()==original[0][:128]
        wr(0,0xd4);vm.cmd('cont');time.sleep(.23);vm.cmd('stop')
        assert rd(5)&2  # Force Interrupt at the next synthetic index pulse.
        rd(0);wr(0,0xd0)
        # Track streams and WD format tokens, for both FM and MFM.
        for drive,mfm,fill in ((0,False,0x6a),(2,True,0x63)):
            seek(drive,0,1);wr(4,drive|(0x20 if mfm else 0))
            length=12500 if mfm else 6250
            wr(0,0xe0);track=bytes(rd(3) for _ in range(length))
            assert not rd(0)&0xdd
            prefix=b'\xa1'*3 if mfm else b''
            id=b'\0\0\x01\0'
            crc=binascii.crc_hqx(prefix+b'\xfe'+id,0xffff)
            assert prefix+b'\xfe'+id+crc.to_bytes(2,'big') in track
            gap=0x4e if mfm else 0xff
            stream=bytearray([gap]*40+[0]*(12 if mfm else 6))
            if mfm:stream.extend([0xf6]*3)
            stream.extend([0xfc]+[gap]*(50 if mfm else 26))
            for sector in range(1,27):
                stream.extend([0]*(12 if mfm else 6))
                if mfm:stream.extend([0xf5]*3)
                stream.extend([0xfe,0,0,sector,0,0xf7]+[gap]*(22 if mfm else 11))
                stream.extend([0]*(12 if mfm else 6))
                if mfm:stream.extend([0xf5]*3)
                stream.extend([0xfb]+[fill]*128+[0xf7]+[gap]*(40 if mfm else 27))
            physical=sum(2 if byte==0xf7 else 1 for byte in stream)
            stream.extend([gap]*(length-physical))
            wr(0,0xf0)
            for byte in stream:wr(3,byte)
            assert not rd(0)&0xdd
            expected[drive][:26*128]=bytes([fill])*(26*128)
            wr(2,1);assert read_sector()==bytes([fill])*128
            wr(2,26);assert read_sector()==bytes([fill])*128
            bad=stream.index(0xf7)
            broken=stream[:bad]+b'\0\0'+stream[bad+1:]
            wr(0,0xf0)
            for byte in broken:wr(3,byte)
            assert rd(0)&8  # Bad ID CRC: original track remains intact.
            wr(2,1);assert read_sector()==bytes([fill])*128
        # The LED decoder is still selected by CS2; CS3 stays disabled.
        for port,value in ((0xaa,0),(0xae,0x80),(0xaf,0xbf),(0xb0,0x28)):
            g.write_memory(0x1000000+port,bytes([value]))
        g.write_memory(0x800000,b'\x7f\x00')
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            info=json.loads(state.read_text())
            if info['enabled'] and info['anode']==127:break
            time.sleep(.02)
        else:raise AssertionError(info)
    finally:g.socket.close();vm.close()
    for drive,path in paths.items():assert path.read_bytes()==expected[drive],drive
    vm,g,state=start()
    try:
        for drive in paths:
            seek(drive,76 if drive<4 else 1023,26 if drive<4 else 32)
            assert read_sector()==bytes(expected[drive][-128:])
    finally:g.socket.close();vm.close()
    print('PASS: WD2797A seek/step/restore, DRQ/INTRQ, six drives, high tracks, sectors, multi-read, ID CRC, FM/MFM track format/read, abort/reset, write protect, restart and LEDs without CS3')
