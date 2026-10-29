"""Prepare a source-debuggable CAMEL24 project and run the complete local stack."""
import argparse
import fcntl
import hashlib
import json
import select
import re
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
MODULES = ['CAMLF91d','CAMLF91e','CAMLF91h','CAMLF91t','cstartup',
           'init_params_f91','vectors24','zsldevinitdummy','poll_bsp']


def win(path):
    return 'Z:'+str(Path(path).resolve()).replace('/','\\')


def prepare(out,zds):
    project = ET.parse(ROOT/'subprojects/CAMELF91_24/camel_f91.zdsproj')
    root = project.getroot(); root.set('configuration','Debug')
    files = root.find('files'); files.clear()
    for module in MODULES: ET.SubElement(files,'file',{'filter-key':''}).text=module+'.asm'
    configs = root.find('configurations')
    for config in list(configs):
        if config.get('name') != 'Debug': configs.remove(config)
    config = configs[0]
    def option(tool,name,value):
        options=config.find(f"./tools/tool[@name='{tool}']/options")
        element=options.find(f"option[@name='{name}']")
        if element is None: element=ET.SubElement(options,'option',{'name':name,'type':'string','change-action':'none'})
        element.text=value
    option('General','outputdir','.\\')
    option('Assembler','include','.;'+win(zds/'include/zilog')+';'+win(zds/'include/std'))
    option('Assembler','define','FLASHED=0,_EZ80ACCLAIM!=1,_DEBUG')
    option('Debugger','target','QEMU_CAMEL24')
    option('Debugger','debugtool','EthernetSmartCable')
    option('Linker','of','camel')
    option('Linker','createnew','false')
    option('Linker','linkctlfile','camel.linkcmd')
    option('Linker','objlibmods',win(zds/'lib/std/chelpD.lib'))
    option('Linker','exeform','OMF695,INTEL32')
    root.find('breakpoints').clear()
    project.write(out/'camel24.zdsproj',encoding='utf-8',xml_declaration=True)
    target=ET.parse(ROOT/'subprojects/CAMELF91_24/eZ80F91_99C0879_Debug.ztgt')
    target.getroot().set('name','QEMU_CAMEL24')
    target.find('./ExtFlash/externalAutoSelect').text='false'
    target.write(out/'QEMU_CAMEL24.ztgt',encoding='utf-8',xml_declaration=True)


def listening(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=.1): return True
    except OSError: return False


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu',type=Path,default=Path(os.environ.get('QEMU_EZ80','/tmp/qemuez80f91-build-baseline/qemu-system-ez80')))
    parser.add_argument('--zds',type=Path,default=Path(os.environ.get('ZDS_HOME',str(Path.home()/'.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5'))))
    parser.add_argument('--wine-prefix',type=Path,default=Path('/tmp/qemuez80f91-zds-wine'))
    parser.add_argument('--no-views',action='store_true',help='Keine Debugansichten automatisch öffnen')
    parser.add_argument('--rebuild',action='store_true')
    parser.add_argument('--prepare-only',action='store_true',help='Build debug files and write the project without launching the GUI')
    parser.add_argument('--port',type=int,choices=[4040],default=4040,help='ZDS Ethernet Smart Cable verwendet Port 4040')
    parser.add_argument('--gdb-port',type=int,default=1234,help='Kompatibilitätsoption; nativer Debugport nutzt einen privaten Unix-Socket')
    parser.add_argument('--uart-port',type=int,default=4444)
    parser.add_argument('--nic',default='none',help='QEMU-MAC-Backend, z.B. socket,connect=127.0.0.1:5555 (Standard: none)')
    for cs in range(4):
        parser.add_argument(f'--cs{cs}',choices=('ram','flash','none'),help='Externer Speichertyp')
    args=parser.parse_args()
    machine='ez80f91-freertos,ram-boot=on'
    machine+=''.join(f',cs{cs}={getattr(args,f"cs{cs}")}' for cs in range(4) if getattr(args,f'cs{cs}'))
    out=ROOT/'build/f24'; out.mkdir(parents=True,exist_ok=True)
    with (out/'start.lock').open('w') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print('CAMEL24 läuft bereits (build/f24/start.lock).',file=sys.stderr); return 1
        for path in [args.qemu,args.zds/'bin/Zds2Ide.exe',args.zds/'bin/nxEz80EthernetSC.dll']:
            if not path.is_file(): parser.error(f'Nicht gefunden: {path}')
        # Debug symbols must come from exactly the patched sources shown in ZDS.
        valid = False
        try:
            metadata=json.loads((out/'camel.json').read_text())
            digest=lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            valid=(out/'camel.lod').exists() and digest(out/'camel.bin') == metadata['binary_sha256']
            valid=valid and digest(ROOT/'patches/camelf91/0001-fix-24bit-core.patch') == metadata['patch_sha256']
            valid=valid and all(digest(out/name)==value for name,value in metadata['sources'].items())
        except (OSError,ValueError,KeyError): valid=False
        if args.rebuild or not valid:
            subprocess.run([sys.executable,str(ROOT/'examples/camelf91/build.py'),
                            '--zds',str(args.zds),'--out',str(out),'--wine-prefix',str(args.wine_prefix),'--debug-info'],check=True)
        prepare(out,args.zds)
        commands=[f'cd "{win(out)}"',f'log "{win(out/"zds-session.log")}"','log on',
                  'open project "camel24.zdsproj"','debugtool set "EthernetSmartCable"',
                  'debugtool set "ipAddress" "127.0.0.1"',
                  'reset','print "F24_READY PC=%x" reg PC','log off']
        (out/'start.cmd').write_text('\n'.join(commands)+'\n')
        if args.prepare_only:
            print(out/'camel24.zdsproj'); return 0
        (out/'start.pid').write_text(str(os.getpid())+'\n')
        children=[]; logs=[]; uart=None
        def stop(signum,frame): raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,stop)
        try:
            for port in (args.port,args.uart_port):
                if listening(port): raise RuntimeError(f'Port {port} ist belegt; vorhandenen Debugstarter zuerst beenden.')
            def launch(command,name,env=None):
                log=(out/(name+'.log')).open('w'); logs.append(log)
                child=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
                children.append(child); return child
            qemu=launch([str(args.qemu),'-M',machine,'-kernel',str(out/'camel.bin'),
                         '-S',f'--dbgport={args.port}','--scan-dev','-display','none','-monitor','none',
                         '-serial',f'tcp:127.0.0.1:{args.uart_port},server=on,wait=off',
                         '-nic',args.nic],'qemu')
            for _ in range(100):
                if qemu.poll() is not None: raise RuntimeError('QEMU beendet: siehe build/f24/qemu.log')
                if listening(args.port): break
                time.sleep(.05)
            else: raise RuntimeError('Nativer ZDS-Debugport startet nicht; siehe qemu.log')
            uart=socket.create_connection(('127.0.0.1',args.uart_port),timeout=5)
            env=dict(os.environ,WINEPREFIX=str(args.wine_prefix.resolve()),WINEDEBUG='-all')
            (out/'zds-session.log').unlink(missing_ok=True)
            launch(['wine',str(args.zds/'bin/Zds2Ide.exe'),'@'+win(out/'start.cmd')],'ide',env)
            print(f'CAMEL24: ZDS II startet mit Quellcode und Ethernet-ZDI 127.0.0.1:{args.port}.',flush=True)
            print(f'Logs: {out}\nStrg-C beendet diesen Start.',flush=True)
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                if any(child.poll() is not None for child in children): raise RuntimeError('Ein Startprozess wurde beendet; siehe Logs.')
                try: status=(out/'zds-session.log').read_text(errors='replace')
                except FileNotFoundError: status=''
                if re.search(r'^F24_READY PC=[0-9a-fA-F]+$',status,re.MULTILINE) and 'Loading file ' in status and ' successful.' in status:
                    if '[ERROR]' in status: raise RuntimeError('ZDS meldet einen Fehler; siehe zds-session.log.')
                    break
                time.sleep(.2)
            else: raise RuntimeError('ZDS-Debugstart nach 90 Sekunden nicht bestätigt; siehe zds-session.log.')
            if not args.no_views:
                source=ROOT/'tools/zds/views.c'; helper=out/'views.exe'
                if not helper.exists() or helper.stat().st_mtime < source.stat().st_mtime:
                    subprocess.run(['i686-w64-mingw32-gcc','-Wall','-Wextra',str(source),'-o',str(helper)],check=True)
                with (out/'views.log').open('w') as view_log:
                    result=subprocess.run(['wine',str(helper),'--open',win(args.zds/'bin/Zds2Ide.exe')],
                                          env=env,stdout=view_log,stderr=subprocess.STDOUT,timeout=120)
                if result.returncode: print('Einige Debugansichten fehlen; siehe build/f24/views.log.',flush=True)
            print('Bereit: CAMEL24 ist in ZDS II am Einstieg angehalten. F5 startet, F11 schaltet einzeln.\nForth-Konsole in diesem Terminal; nach Go können Befehle eingegeben werden.',flush=True)
            inputs=[uart]
            if sys.stdin.isatty(): inputs.append(sys.stdin)
            while all(child.poll() is None for child in children):
                ready,_,_=select.select(inputs,[],[],.2)
                if uart in ready:
                    data=uart.recv(4096)
                    if not data: raise RuntimeError('UART-Verbindung beendet')
                    print(data.decode('latin-1'),end='',flush=True)
                if sys.stdin in ready:
                    line=sys.stdin.readline()
                    if not line: inputs.remove(sys.stdin)
                    else: uart.sendall(line.rstrip('\r\n').encode('latin-1')+b'\r')
            return next((c.returncode for c in children if c.returncode),0)
        except KeyboardInterrupt: return 0
        except RuntimeError as error:
            print(error,file=sys.stderr); return 1
        finally:
            if uart: uart.close()
            for child in reversed(children):
                if child.poll() is None: child.terminate()
            for child in reversed(children):
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired: child.kill(); child.wait()
            for log in logs: log.close()


if __name__ == "__main__":
    sys.exit(main())
