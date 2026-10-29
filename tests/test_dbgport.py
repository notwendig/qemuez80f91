#!/usr/bin/env python3
"""Native --dbgport=PORT, UDP Scan Device, packaging and managed lifetime."""
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from ez80_testlib import VM, binary

root = Path(__file__).resolve().parents[1]
for name in ('ethernet.py','rsp.py','dtl.py','zdi.py'):
    assert (root/'tools/zds'/name).read_bytes() == (root/'qemu/pc-bios/ez80-zds'/name).read_bytes(), name

def exact(sock,n):
    data=b''
    while len(data)<n:
        part=sock.recv(n-len(data))
        assert part,'debugger socket closed early'
        data+=part
    return data

with tempfile.TemporaryDirectory(prefix='f91-dbgport-') as td:
    bios=Path(td)/'halt.bin';bios.write_bytes(bytes([0x76]))
    for port in ('0','65536','x','123x'):
        p=subprocess.run([binary,'-M','ez80f91-minimal','-bios',str(bios),f'--dbgport={port}',
                          '-display','none','-serial','none'],capture_output=True,text=True,timeout=5)
        assert p.returncode and '1..65535' in p.stderr,(port,p.stderr)
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
    vm=VM(bios,extra=(f'--dbgport={port}','--scan-dev','-nic','none'))
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as scan:
            scan.bind(('127.0.0.1',0));scan.settimeout(.25)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                scan.sendto(b'scan',('127.0.0.1',3000))
                try:
                    reply,address=scan.recvfrom(512)
                    fields=reply.decode().split(',')
                    if fields[-1]==str(port):break
                except socket.timeout:pass
            else:raise AssertionError('No native Scan Device response')
            assert fields[0]=='100' and fields[1]=='QEMU-eZ80F91' and address[1]==3000,reply
        with socket.create_connection(('127.0.0.1',port),timeout=3) as cable:
            script=b'. []=R00 []=R01 []=R02 $\0'
            cable.sendall((len(script)+3).to_bytes(2,'little')+b'\0'+script)
            header=exact(cable,3);assert header[2]==0
            assert exact(cable,int.from_bytes(header[:2],'little')-3)==b'000003080001\0'
        assert 'PC=000000' in vm.hmp('info registers'),'dbgport should start halted'
    finally:vm.close()
    with socket.socket() as check:
        check.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        check.bind(('0.0.0.0',port))
    print('PASS: --dbgport=PORT validation, SDK UDP Scan Device, DTL identity and cleanup')
    # Without -S, native dbgport preserves normal guest autostart.
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
    vm=VM.__new__(VM)
    vm.p=subprocess.Popen([binary,'-M','ez80f91-minimal','-bios',str(bios),
        f'--dbgport={port}','-display','none','-serial','none','-monitor','none',
        '-nic','none','-qmp','stdio'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    vm.buffer=b''
    try:
        assert 'QMP' in vm.read();vm.cmd('qmp_capabilities')
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1) as cable:
                    script=b'. []=R00 $\0'
                    cable.sendall((len(script)+3).to_bytes(2,'little')+b'\0'+script)
                    header=exact(cable,3)
                    assert exact(cable,int.from_bytes(header[:2],'little')-3)==b'00000108\0'
                    break
            except ConnectionRefusedError:time.sleep(.05)
        else:raise AssertionError('Autostart helper did not become ready')
        vm.halted()
        assert 'PC=000001' in vm.hmp('info registers'),'guest did not autostart'
    finally:vm.close()
    print('PASS: native dbgport preserves autostart without -S')

