#!/usr/bin/env python3
"""F91 RTC: ZTP register ABI, write locking, binary/BCD rollover and reset retention."""
from pathlib import Path
from datetime import datetime, timezone
import socket
import sys
import tempfile
import time
from ez80_testlib import VM
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/zds'))
from rsp import RSP

with tempfile.TemporaryDirectory(prefix='f91-rtc-') as td:
    root=Path(td);rom=root/'loop.bin'
    rom.write_bytes(bytes.fromhex('5bc3050000c3050000'))
    path=root/'gdb.sock'
    before_host=datetime.now(timezone.utc).timestamp()
    vm=VM(rom,extra=('-gdb',f'unix:{path},server=on,wait=off','-nic','none','-rtc','base=utc,clock=vm'))
    g=RSP(unix=str(path))
    def read():return g.memory(0x10000e0,14)
    def write(reg,value):g.write_memory(0x1000000+reg,bytes([value]))
    def setdate(values,bcd=False):
        write(0xed,0x21 if bcd else 1)
        for reg,value in enumerate(values):write(0xe0+reg,value)
        write(0xed,0x20 if bcd else 0)
    def advance():
        vm.cmd('cont');time.sleep(2.1);vm.cmd('stop')
    try:
        initial=read()
        host_date=datetime(initial[7]*100+initial[6],initial[5],initial[4],
                           initial[2],initial[1],initial[0],tzinfo=timezone.utc)
        assert before_host-1<=host_date.timestamp()<=datetime.now(timezone.utc).timestamp()+1
        assert initial[3]==host_date.isoweekday(),initial.hex()
        print('PASS: RTC startup date/time and weekday initialized from host UTC')
        # Binary values are exactly the byte-oriented ABI used by ZTP RTC_SET_ALL.
        values=bytes([59,59,23,4,28,2,24,20]);setdate(values)
        assert read()[:8]==values
        write(0xe0,12);assert read()[0]==59 # locked writes ignored
        write(0xed,1);advance();assert read()[:8]==values # unlocked freezes
        write(0xed,0);advance();b=read()
        assert b[1:8]==bytes([0,0,5,29,2,24,20]),b.hex()
        assert 0<=b[0]<=2,b.hex()
        print('PASS: RTC byte ABI, lock/freeze, leap-day rollover')
        setdate(bytes.fromhex('5959230431122520'),True);advance();b=read()
        assert b[1:8]==bytes.fromhex('00000501012620'),b.hex()
        assert 0<=b[0]<=2 and b[13]&0x20,b.hex()
        before=read()[:8];vm.cmd('system_reset');assert read()[:8]==before
        assert read()[13]==0x20
        print('PASS: BCD year/century representation and warm-reset retention')
    finally:g.socket.close();vm.close()
