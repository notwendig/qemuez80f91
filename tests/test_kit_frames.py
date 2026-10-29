#!/usr/bin/env python3
"""The kit panel holds its last full image through partial/paused row scans."""
import json
from pathlib import Path
import sys
import tempfile
import time
from ez80_testlib import VM
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/zds'))
from rsp import RSP

with tempfile.TemporaryDirectory(prefix='f91-kit-frames-') as td:
    root=Path(td);rom=root/'idle.bin';rom.write_bytes(b'\x76')
    state=root/'kit.json';gdb=root/'gdb.sock'
    vm=VM(rom,extra=('-nic','none','-gdb',f'unix:{gdb},server=on,wait=off',
                    '-icount','shift=10,sleep=off',
                    '-global',f'ez80f91-memory.kit-led-state={state}'))
    g=RSP(unix=str(gdb))
    def io(port,value):g.write_memory(0x1000000+port,bytes([value]))
    def mask(rows):
        return sum(1<<(r*5+c) for r in range(7) for c in range(5) if rows[r]&(1<<(4-c)))
    def observe(expected, update=False):
        # Several GUI polls while the guest is frozen must never reveal a row.
        if update:
            end=time.monotonic()+2
            while time.monotonic()<end:
                try:
                    if int(json.loads(state.read_text())['mask'],16)==expected:break
                except (ValueError,OSError):pass
                time.sleep(.01)
            else:raise AssertionError(('complete frame not published',hex(expected)))
        end=time.monotonic()+.12;seen=False
        while time.monotonic()<end:
            try:data=json.loads(state.read_text())
            except (ValueError,OSError):continue
            assert int(data['mask'],16)==expected,(hex(expected),data)
            seen=True;time.sleep(.01)
        assert seen
    def stopped(pc):
        end=time.monotonic()+5
        while g.running and time.monotonic()<end:
            g.poll();time.sleep(.001)
        assert not g.running,'guest row checkpoint timeout'
        assert g.registers()[0]==pc
    try:
        io(0xaa,0);io(0xae,0x80);io(0xaf,0xbf);io(0xb0,0x28)
        # Continuous scrolling: every complete frame differs. Requiring
        # identical consecutive scans would freeze this sequence indefinitely.
        old=[2,4,8,16,8,4,2]
        new=[1,2,4,8,4,2,1]
        torn=old[:3]+new[3:]
        frames=[old,torn,new,[0,1,2,4,2,1,0],[0]*7]
        expected_frames=frames
        code=bytearray();points=[]
        def store(addr,value):code.extend((0x3e,value,0x32,*addr.to_bytes(3,'little')))
        base=0xa00000
        for frame in frames:
            for row,bits in enumerate(frame):
                store(0x800000,0)
                store(0x800001,bits^31)
                store(0x800000,1<<row)
                # >40 ms guest time per row: catches the previous timed
                # integration even when the GUI polls between every row.
                code.extend((0x01,0x50,0xc3,0)) # BC=50000, ADL
                code.extend(bytes.fromhex('0b78b120fb'))
                store(0x800000,0)
                points.append(base+len(code));code.append(0)
        code.append(0x76)
        g.write_memory(base,code)
        for pc in points:assert g.command(f'Z0,{pc:x},1')=='OK'
        regs=g.registers();regs[0]=base;regs[18]=1;g.set_registers(regs)
        displayed=0
        for index,pc in enumerate(points):
            g.run();stopped(pc)
            frame,row=divmod(index,7)
            if row==6:displayed=mask(expected_frames[frame])
            observe(displayed,update=row==6)
            g.step()
        print('PASS: every changing scrolling frame is published after all seven rows; no identical scans required')
        vm.cmd('system_reset')
        time.sleep(.06);observe(0)
        print('PASS: paused scans keep full image; reset clears panel')
    finally:g.socket.close();vm.close()
