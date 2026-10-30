#!/usr/bin/env python3
"""Exercise the patched CamelForth kernel through UART, including reset."""
import hashlib
import json
from pathlib import Path
import re
import select
import socket
import sys
import tempfile
import time
from ez80_testlib import VM

base=Path(__file__).resolve().parents[1]/'examples/camelf91'
fixture=Path(sys.argv[2]) if len(sys.argv)>2 else base/'camel.bin'
meta=json.loads(fixture.with_suffix('.json').read_text())
assert hashlib.sha256(fixture.read_bytes()).hexdigest()==meta['binary_sha256']
assert meta['upstream_commit']=='af47e6520adc220cef5ee7e9ab96f0c336f7e299'
for name in ('kit.inc','kit_font.inc'):
    assert meta['sources'][name]==hashlib.sha256((base/name).read_bytes()).hexdigest(),name
cases=json.loads((base/'commands.json').read_text())
banner=b'\r\n\r\neZ80F91 Camel FORTH 1.1.0 (24bit) - Debug, 16.09.2021 12:31:21 CEST\r\n'
with tempfile.TemporaryDirectory(prefix='f91-camel-') as td:
    root=Path(td); endpoint=root/'uart.sock'
    vm=VM(fixture,'unix:'+str(endpoint)+',server=on,wait=off',
          extra=('-icount','shift=0'),machine=meta['board'],loader='-kernel')
    sock=socket.socket(socket.AF_UNIX); sock.connect(str(endpoint)); sock.setblocking(False)
    def receive(expected):
        data=bytearray(); deadline=time.monotonic()+10
        while len(data)<len(expected) and time.monotonic()<deadline:
            if select.select([sock],[],[],.05)[0]:
                chunk=sock.recv(65536)
                if not chunk: raise AssertionError(('UART closed',bytes(data)))
                data.extend(chunk)
        assert bytes(data)==expected,(bytes(data),expected)
    def memory(address,size):
        target=root/'memory.bin'
        vm.cmd('pmemsave',{'val':address,'size':size,'filename':str(target)})
        return target.read_bytes()
    def number(address): return int.from_bytes(memory(address,3),'little')
    def regs():
        return {k:int(v,16) for k,v in re.findall(r'([A-Z0-9]+)=([0-9a-f]+)',vm.hmp('info registers'))}
    try:
        for iteration in range(2):
            vm.cmd('cont'); receive(banner); vm.cmd('stop')
            initial_dp=number(meta['symbols']['defuser']+12)
            assert number(meta['symbols']['user0']+12)==initial_dp
            assert number(meta['symbols']['user0']+6)==10
            vm.cmd('cont')
            for case in cases:
                command=case['command'].encode()
                sock.sendall(command+b'\r'+case.get('input','').encode())
                receive(command+b' '+case['result'].encode()+b'\r\nOK ')
            sock.sendall(b'bye\r'); receive(b'bye '); vm.halted(); vm.cmd('stop')
            state=regs()
            assert state['PC']==meta['symbols']['BYE']+1,state
            assert state['ADL']==1 and state['IY']==meta['symbols']['user0'],state
            assert number(meta['symbols']['user0']+12)>initial_dp
            assert number(meta['symbols']['user0']+6)==10
            if iteration==0: vm.cmd('system_reset')
    finally:
        sock.close(); vm.close()
print(f'PASS: CamelForth {len(cases)} cases twice, DEPTH/FM-MOD/M+/ACCEPT, math, compile, UART, reset')
