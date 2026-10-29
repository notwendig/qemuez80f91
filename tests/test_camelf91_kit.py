#!/usr/bin/env python3
"""Native CamelForth button polling and live Timer1-driven 5x7 glyphs."""
import argparse
import json
from pathlib import Path
import re
import select
import socket
import subprocess
import sys
import tempfile
import time
import ez80_testlib

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('qemu',type=Path)
    p.add_argument('--hex',type=Path,default=ROOT/'subprojects/CAMELF91_24/Debug/camel_f91.hex')
    p.add_argument('--map',type=Path,default=ROOT/'subprojects/CAMELF91_24/Debug/camel_f91.map')
    args=p.parse_args();ez80_testlib.binary=str(args.qemu.resolve())
    symbols={n:int(a,16) for n,a in re.findall(r'^(\S+)\s+[CD]:([0-9A-F]+)\b',args.map.read_text(),re.M)}
    with tempfile.TemporaryDirectory(prefix='f91-forth-kit-') as td:
        root=Path(td);image=root/'camel.bin';state=root/'kit.json';endpoint=root/'uart.sock'
        subprocess.run([sys.executable,str(ROOT/'scripts/ihex_to_bin.py'),str(args.hex),str(image)],check=True)
        vm=ez80_testlib.VM(image,'unix:'+str(endpoint)+',server=on,wait=off',
            extra=('-nic','none','-icount','shift=5,sleep=off',
                   '-global',f'ez80f91-memory.kit-led-state={state}'),
            machine='ez80f91-freertos,ram-boot=on',loader='-kernel')
        sock=socket.socket(socket.AF_UNIX);sock.connect(str(endpoint));sock.setblocking(False)
        pending=bytearray()
        def until(end):
            deadline=time.monotonic()+10
            while not pending.endswith(end):
                if time.monotonic()>deadline:raise AssertionError(('UART timeout',bytes(pending)))
                if select.select([sock],[],[],.05)[0]:
                    b=sock.recv(65536)
                    assert b,'UART closed'
                    pending.extend(b)
            result=bytes(pending);pending.clear();return result
        def command(c,result=''):
            assert len(c)<=124
            sock.sendall(c.encode()+b'\r')
            expected=c.encode()+b' '+result.encode()+b'\r\nOK '
            actual=until(b'\r\nOK ')
            assert actual==expected,(c,actual,expected)
        def wait_rows(rows):
            mask=sum(1<<(r*5+c) for r in range(7) for c in range(5) if rows[r]&(1<<(4-c)))
            end=time.monotonic()+8;data=None
            while time.monotonic()<end:
                try:
                    data=json.loads(state.read_text())
                    if data['enabled'] and int(data['mask'],16)==mask:return
                except (ValueError,OSError):pass
                time.sleep(.02)
            raise AssertionError(('matrix',hex(mask),data))
        def pixels():
            path=root/'pixels.bin'
            vm.cmd('pmemsave',{'val':symbols['kit_matrix_pixels'],'size':7,'filename':str(path)})
            return list(path.read_bytes())
        try:
            vm.cmd('cont');until(b'CEST\r\n')
            children=vm.cmd('qom-list',{'path':'/machine/unattached'})
            memory=next(c['name'] for c in children if c['type']=='child<ez80f91-memory>')
            def buttons(mask):
                vm.cmd('qom-set',{'path':'/machine/unattached/'+memory,'property':'kit-buttons','value':mask})
            command('160 155 P0! 64 156 P0! 128 157 P0! BUTTON-INIT')
            command('155 P0@ . 156 P0@ . 157 P0@ .','167 64 128 ')
            for mask in range(8):
                buttons(mask)
                flags=[-1 if mask&(1<<i) else 0 for i in range(3)]
                command('BUTTONS . SW1? . SW2? . SW3? .',str(mask)+' '+''.join(str(f)+' ' for f in flags))
                command('1 BUTTON? . 2 BUTTON? . 3 BUTTON? .',''.join(str(f)+' ' for f in flags))
            buttons(0)
            command('0 BUTTON? . 4 BUTTON? . -1 BUTTON? . 16777215 BUTTON? .','0 0 0 0 ')
            print('PASS: all eight simultaneous button masks, release, valid/invalid indices, PB3..7 preserved',flush=True)
            command('MATRIX-INIT');wait_rows([0]*7)
            glyphs=[('CHAR A',[14,17,17,31,17,17,17]),('CHAR a',[14,17,17,31,17,17,17]),
                    ('CHAR 0',[14,17,19,21,25,17,14]),('32',[0]*7),
                    ('126',[0,0,8,21,2,0,0]),('0',[14,17,1,2,4,0,4]),
                    ('127',[14,17,1,2,4,0,4]),('-1',[14,17,1,2,4,0,4]),
                    ('256',[14,17,1,2,4,0,4])]
            for value,rows in glyphs:
                command(value+' MATRIX-CHAR')
                assert pixels()==rows,(value,pixels(),rows)
                wait_rows(rows)
            command('CHAR A MATRIX-CHAR MATRIX-INIT')
            wait_rows([14,17,17,31,17,17,17])
            command(': WORK 0 1000 0 DO I + LOOP ; WORK .','499500 ')
            command('DEPTH .','0 ')
            wait_rows([14,17,17,31,17,17,17])
            print('PASS: ASCII glyphs, fallback, pixel orientation, persistent refresh, idempotent init, console/stack under IRQ load',flush=True)
            rows=[16,8,4,2,1,0,31]
            command('CREATE PIX '+''.join(str(n)+' C, ' for n in rows)+'PIX MATRIX!')
            wait_rows(rows)
            command('MATRIX-CLEAR');wait_rows([0]*7)
            command('101 P0@ 1 AND .','1 ')
            command('MATRIX-OFF');wait_rows([0]*7)
            command('101 P0@ . 102 P0@ .','0 0 ')
            command('CHAR A MATRIX-CHAR');wait_rows([14,17,17,31,17,17,17])
            command('MATRIX-OFF');wait_rows([0]*7)
            vm.cmd('stop');vm.cmd('system_reset');vm.cmd('cont');until(b'CEST\r\n')
            command('BUTTONS .','0 ')
            command('101 P0@ . 102 P0@ .','0 0 ')
            command('CHAR 0 MATRIX-CHAR');wait_rows([14,17,19,21,25,17,14])
            command('MATRIX-OFF')
            print('PASS: custom bitmap, clear, timer off/on, hardware reset and reinitialization',flush=True)
        finally:
            sock.close();vm.close()

if __name__=='__main__':main()
