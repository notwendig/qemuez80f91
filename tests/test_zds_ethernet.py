#!/usr/bin/env python3
"""Integration test: installed PE32 Nexus DLL → Ethernet → ZDI → QEMU."""
import argparse
import logging
import re
import select
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/zds'))
from ethernet import session
from dtl import DTL
from zdi import ZDI
from rsp import RSP


def windows(path):
    return 'Z:'+str(Path(path).resolve()).replace('/','\\')


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def native_probe(args, work, probe, bios, dll, ini):
    sys.path.insert(0,str(ROOT/'tests'))
    import ez80_testlib
    ez80_testlib.binary = str(Path(args.qemu).resolve())
    port = free_port()
    vm = ez80_testlib.VM(bios,extra=(f'--dbgport={port}','--scan-dev','-nic','none'))
    try:
        for _ in range(100):
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1): pass
                break
            except OSError:
                if vm.p.poll() is not None: raise RuntimeError(vm.p.stderr.read().decode())
                time.sleep(.05)
        else: raise RuntimeError('native dbgport startup timed out')
        env = dict(os.environ,WINEPREFIX=str(Path(args.wine_prefix).resolve()),WINEDEBUG='-all')
        if args.sdk_scan:
            scanner = subprocess.Popen(['wine',str(args.sdk/'bin/escscan.exe'),'127.0.0.1'],
                                       env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
            output = b''
            try:
                deadline = time.monotonic()+45
                while time.monotonic()<deadline:
                    if not select.select([scanner.stdout],[],[],.2)[0]: continue
                    data = scanner.stdout.read1(4096)
                    if not data: break
                    output += data
                    if b'QEMU-eZ80F91' in output and str(port).encode() in output: break
                print(output.decode(errors='replace'),flush=True)
                assert b'QEMU-eZ80F91' in output and str(port).encode() in output,'Original SDK scanner did not find QEMU'
                print('PASS: original SDK escscan.exe discovers native dbgport')
            finally:
                if scanner.poll() is None: scanner.terminate()
                try: scanner.wait(timeout=5)
                except subprocess.TimeoutExpired: scanner.kill();scanner.wait()
        result = subprocess.run(['wine',str(probe),windows(dll),windows(ini),str(port)],
                                env=env,capture_output=True,text=True,timeout=45)
        print(result.stdout,end='')
        if result.stderr: print(result.stderr,file=sys.stderr,end='')
        assert result.returncode == 0,result.returncode
        state = vm.hmp('info registers')
        regs = {k:int(v,16) for k,v in re.findall(r'([A-Z0-9]+)=([0-9a-f]+)',state)}
        assert 0xffe000 <= regs['PC'] <= 0xffe003 and regs['AF'] >> 8 == 0x42,state
        saved = work/'native-memory.bin'
        vm.cmd('pmemsave',{'val':0xffe000,'size':5,'filename':str(saved)})
        assert saved.read_bytes()==bytes([0,0x3e,0x42,0x18,0xfb])
        print('PASS: native dbgport independent QMP CPU/RAM verification')
    finally: vm.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu',default='/tmp/qemuez80f91-build-baseline/qemu-system-ez80')
    parser.add_argument('--sdk',type=Path,default=ROOT.parent/'NexusSDK_1.1')
    parser.add_argument('--zds',type=Path,default=Path.home()/'.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5')
    parser.add_argument('--wine-prefix',default='/tmp/qemuez80f91-zds-wine')
    parser.add_argument('--native',action='store_true',help='Test QEMU --dbgport instead of an external bridge')
    parser.add_argument('--sdk-scan',action='store_true',help='Also run original SDK escscan.exe')
    parser.add_argument('--verbose',action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.ERROR)
    dll = args.zds/'bin/nxEz80EthernetSC.dll'
    ini = args.zds/'config/eZ80F91algo.ini'
    for path in (dll,ini,args.sdk/'include/nxapi.h',Path(args.qemu)):
        if not path.is_file(): parser.error(f'not found: {path}')
    with tempfile.TemporaryDirectory(prefix='ez80-zdi-') as directory:
        work = Path(directory); probe = work/'probe.exe'; bios = work/'probe.bin'
        bios.write_bytes(bytes([0,0,0,0x18,0xfb]))
        subprocess.run(['i686-w64-mingw32-gcc','-Wall','-Wextra','-fpack-struct=4',
                        '-I'+str(args.sdk/'include'),str(ROOT/'tests/zds_nexus/probe.c'),
                        '-o',str(probe)],check=True)
        if args.native:
            native_probe(args,work,probe,bios,dll,ini)
            return
        port = free_port()
        qemu = subprocess.Popen([args.qemu,'-M','ez80f91-minimal','-bios',str(bios),
                  '-S','-gdb',f'tcp:127.0.0.1:{port}','-display','none',
                  '-serial','none','-monitor','none'],stderr=subprocess.PIPE)
        rsp = None
        try:
            for _ in range(100):
                try: rsp = RSP('127.0.0.1',port); break
                except ConnectionRefusedError:
                    if qemu.poll() is not None: raise RuntimeError(qemu.stderr.read().decode())
                    time.sleep(.05)
            if rsp is None: raise RuntimeError('QEMU GDB startup timed out')
            assert len(rsp.registers()) == 24
            errors = []
            with socket.socket() as server:
                server.bind(('127.0.0.1',0)); server.listen(1); server.settimeout(30)
                def serve():
                    try:
                        client,_ = server.accept()
                        with client:
                            client.settimeout(30)
                            try: session(client,DTL(ZDI(rsp)))
                            except EOFError: pass
                    except Exception as error: errors.append(error)
                thread = threading.Thread(target=serve,daemon=True); thread.start()
                env = dict(os.environ,WINEPREFIX=str(Path(args.wine_prefix).resolve()),WINEDEBUG='-all')
                result = subprocess.run(['wine',str(probe),windows(dll),windows(ini),
                            str(server.getsockname()[1])],env=env,capture_output=True,text=True,timeout=45)
                print(result.stdout,end='')
                if result.stderr: print(result.stderr,file=sys.stderr,end='')
                thread.join(timeout=2)
                if errors: raise errors[0]
                assert result.returncode == 0, f'Nexus probe failed: {result.returncode}'
                assert not thread.is_alive(), 'Ethernet session did not close'
                r = rsp.registers()
                assert 0xffe000 <= r[0] <= 0xffe003 and r[12] == 0x42, r
                assert rsp.memory(0xffe000,5) == bytes([0,0x3e,0x42,0x18,0xfb])
                print('PASS: independent QEMU CPU/RAM verification')
        finally:
            if rsp: rsp.socket.close()
            qemu.terminate()
            try: qemu.wait(timeout=5)
            except subprocess.TimeoutExpired: qemu.kill(); qemu.wait()
            qemu.stderr.close()

if __name__ == '__main__': main()
