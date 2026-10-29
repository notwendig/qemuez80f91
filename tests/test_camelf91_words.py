#!/usr/bin/env python3
"""Run the pasteable CamelForth suite and measure entry coverage of its ROM dictionary."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import select
import socket
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'examples/camelf91'))
from word_tests import SETUP, CASES, INTERACTIVE, export
import ez80_testlib


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('qemu',type=Path)
    p.add_argument('--hex',type=Path,default=ROOT/'subprojects/CAMELF91_24/Debug/camel_f91.hex')
    p.add_argument('--map',type=Path,default=ROOT/'subprojects/CAMELF91_24/Debug/camel_f91.map')
    p.add_argument('--out',type=Path,default=ROOT/'build/camelf91-words')
    args=p.parse_args()
    args.out=args.out.resolve();args.out.mkdir(parents=True,exist_ok=True)
    export()
    image=args.out/'camel.bin'
    subprocess.run([sys.executable,str(ROOT/'scripts/ihex_to_bin.py'),str(args.hex),str(image)],check=True)
    rom=image.read_bytes();maptext=args.map.read_text()
    symbols={n:int(a,16) for n,a in re.findall(r'^(\S+)\s+[CD]:([0-9A-F]+)\b',maptext,re.M)}
    dictionary=[];nfa=symbols['lastword'];seen=set()
    while nfa:
        assert nfa not in seen,'dictionary cycle'
        seen.add(nfa)
        length=rom[nfa]&127
        name=rom[nfa+1:nfa+1+length].decode('ascii')
        dictionary.append(dict(name=name,nfa=nfa,xt=nfa+1+length))
        nfa=int.from_bytes(rom[nfa-4:nfa-1],'little')
    assert len(dictionary)>150
    # Stream the trace: keep hit counts and one execution witness per entry
    # instead of hundreds of MB of repeated interpreter/compiler calls.
    hits=Counter()
    pattern=re.compile(r'\[[0-9a-fA-F]+/([0-9a-fA-F]+)/')
    trace_read,trace_write=os.pipe()
    def collect_trace():
        with os.fdopen(trace_read) as source, (args.out/'entry-trace.log').open('w') as dest:
            for line in source:
                match=pattern.search(line)
                if match:
                    address=int(match[1],16)
                    if not hits[address]:dest.write(line)
                    hits[address]+=1
    collector=threading.Thread(target=collect_trace,daemon=True)
    collector.start()
    ranges=','.join(f"0x{w['xt']:x}+1" for w in dictionary)
    endpoint=args.out/'uart.sock';endpoint.unlink(missing_ok=True)
    ez80_testlib.binary=str(args.qemu.resolve())
    try:
        vm=ez80_testlib.VM(image,'unix:'+str(endpoint)+',server=on,wait=off',
            extra=('-icount','shift=0','-d','exec,nochain','-dfilter',ranges,
                   '-D',f'/proc/self/fd/{trace_write}',
                   '-global',f"ez80f91-memory.kit-led-state={args.out/'kit.json'}"),pass_fds=(trace_write,),
            machine='ez80f91-freertos,ram-boot=on',loader='-kernel')
    finally:
        os.close(trace_write)
    sock=socket.socket(socket.AF_UNIX);sock.connect(str(endpoint));sock.setblocking(False)
    log=(args.out/'uart.log').open('wb');failures=[];completed=[]
    banner=b'\r\n\r\neZ80F91 Camel FORTH 1.1.0 (24bit) - Debug, 16.09.2021 12:31:21 CEST\r\n'
    pending=bytearray()
    def until(end,timeout=15):
        deadline=time.monotonic()+timeout
        while not pending.endswith(end):
            if time.monotonic()>deadline: raise AssertionError(('UART timeout',bytes(pending)))
            if select.select([sock],[],[],.05)[0]:
                b=sock.recv(65536)
                if not b: raise AssertionError('UART closed')
                pending.extend(b);log.write(b);log.flush()
        data=bytes(pending);pending.clear();return data
    def send(command,expected='',input='',suffix=b'\r\nOK '):
        sock.sendall(command.encode()+b'\r'+input.encode())
        result=until(suffix)
        want=command.encode()+b' '+(expected or '').encode()+suffix
        if expected is not None and result!=want:
            failures.append(dict(command=command,expected=want.decode('latin1'),actual=result.decode('latin1')))
            print('FAIL:',command,repr(result),flush=True)
        completed.append(command)
        return result
    tests=0
    try:
        vm.cmd('cont');assert until(banner)==banner
        for line in SETUP:send(line)
        for i,case in enumerate(CASES+INTERACTIVE,1):
            send(case['command'],case['result'],case.get('input',''))
            if case['command'].startswith('T{'):tests+=1
            if i%40==0:print(f'{i}/{len(CASES+INTERACTIVE)} commands',flush=True)
        send('TEST-REPORT',f'\r\nTESTS {tests} FAILURES 0 \r\n')
        # Extra interactive reports, restarts and termination are separate from
        # the pasteable file because they replace the interpreter or need input.
        words=send('WORDS',expected=None)  # Validated against the dictionary below.
        listed=words[len(b'WORDS '):-len(b'\r\nOK ')].decode().split()
        missing=set(w['name'] for w in dictionary)-set(listed)
        if missing:failures.append(dict(command='WORDS',missing=sorted(missing)))
        # MEMCFG and DUMP include addresses; validate their structure and data.
        data=send('MEMCFG',expected=None)
        if not all(x in data for x in (b'TIB:',b'S0:',b'R0:',b'DP:')):
            failures.append(dict(command='MEMCFG',actual=data.decode('latin1')))
        data=send('WB 15 + -16 AND DUP 16 65 FILL 16 DUMP DECIMAL',expected=None)
        if b'41 41 41' not in data or b'AAAAAAAAAAAAAAAA' not in data:
            failures.append(dict(command='DUMP',actual=data.decode('latin1')))
        # QUIT discards the remainder of the input and waits for a new line.
        for restart in ('QUIT','123 ABORT'):
            sock.sendall(restart.encode()+b'\r')
            assert until(restart.encode()+b' ')==restart.encode()+b' '
            send('')
        send('DEPTH .','0 ')
        send(': WRABORT -1 ABORT" EXPECTED-ABORT" ;')
        sock.sendall(b'WRABORT\r')
        assert until(b'EXPECTED-ABORT')==b'WRABORT EXPECTED-ABORT'
        send('')
        send('DEPTH .','0 ')
        sock.sendall(b'COLD\r');data=until(banner)
        if data!=b'COLD '+banner:failures.append(dict(command='COLD',actual=data.decode('latin1')))
        send('DEPTH .','0 ')
        # Dictionary initialization must discard definitions added by the suite.
        send(': WRLOOK BL WORD FIND NIP . ; WRLOOK WRCONST','0 ')
        sock.sendall(b'bye\r');assert until(b'bye ')==b'bye '
        vm.halted();vm.cmd('stop')
        state=vm.hmp('info registers')
        assert f"PC={symbols['BYE']+1:06x}" in state,state
    finally:
        sock.close();log.close();vm.close();endpoint.unlink(missing_ok=True)
        collector.join(timeout=10)
        assert not collector.is_alive(),'trace reader did not finish'
    for w in dictionary:w['entry_hits']=hits[w['xt']]
    uncovered=[w['name'] for w in dictionary if not w['entry_hits']]
    report=dict(image_sha256=hashlib.sha256(rom).hexdigest(),assertions=tests,
                commands=len(completed),failures=failures,dictionary=dictionary,
                uncovered=uncovered,
                coverage_note='Executed ROM word entries, including indirect compiler/interpreter calls; this is not exhaustive input/path coverage.')
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    summary=f"{tests} assertions; {len(failures)} failures; {len(dictionary)-len(uncovered)}/{len(dictionary)} ROM word entries executed"
    markdown=['# CAMELF91 word test', '', summary, '',
              'Entry coverage includes indirect compiler/interpreter calls. It does not cover every input or execution path.', '',
              '| Word | Executed entries |', '| --- | ---: |']
    markdown += [f"| `{w['name']}` | {w['entry_hits']} |" for w in sorted(dictionary,key=lambda w:w['name'].upper())]
    (args.out/'report.md').write_text('\n'.join(markdown)+'\n')
    print(summary)
    if uncovered:print('NOT EXECUTED:',', '.join(uncovered))
    if failures or uncovered:raise SystemExit(1)
    print('PASS:',args.out/'report.json')

if __name__=='__main__':main()
