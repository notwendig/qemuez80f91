#!/usr/bin/env python3
"""Build pinned CamelForth Debug with reviewed core fixes and a polling BSP."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

COMMIT = 'af47e6520adc220cef5ee7e9ab96f0c336f7e299'
ROOT = Path(__file__).resolve().parents[2]
KIT_INCLUDE = b'    .INCLUDE "kit.inc"\r\n\r\n'

def wine_path(p): return 'Z:' + str(p.resolve()).replace('/', '\\')

def build(args):
    source = args.source.resolve(); out = args.out.resolve(); zds = args.zds.resolve()
    if out == source or source in out.parents:
        raise ValueError('Build output must be outside the source checkout')
    actual = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    subprocess.run(['git','-C',str(source),'merge-base','--is-ancestor',COMMIT,actual],check=True)
    out.mkdir(parents=True,exist_ok=True)
    source_files = subprocess.check_output(
        ['git','-C',str(source),'ls-tree','-r','--name-only',COMMIT,'asm'],
        text=True).splitlines()
    input_names = []
    for filename in source_files:
        path = source/filename
        if path.suffix in ('.asm','.inc'):
            # Always derive the reviewed build from the pinned upstream bytes.
            original = subprocess.check_output(
                ['git','-C',str(source),'show',COMMIT+':'+filename])
            (out/path.name).write_bytes(original)
            input_names.append(path.name)
    for filename in source_files:
        path = source/filename
        if path.suffix in ('.asm','.inc'):
            if path.read_bytes() != (out/path.name).read_bytes():
                raise ValueError('Unreviewed assembly changes: '+filename)
    # The polling BSP initializes UART0 itself; omit the native UART startup.
    low = out/'CAMLF91e.asm'
    native = low.read_bytes()
    start = native.index(b'\tSEGMENT TEXT\r\n; UART0 configuration')
    end = native.index(b'\tSEGMENT CODE', start)
    native = native[:start] + native[end:]
    native = native.replace(b'\t.INCLUDE "uart.inc"\r\n', b'')
    low.write_bytes(native.replace(
        b'\tld iy,camel_uart0cfg\r\n\tcall init_uart0\r\n', b''))
    # The native project and polling build share the same reviewed kit driver.
    for name in ('kit.inc','kit_font.inc'):
        asset = Path(__file__).parent/name
        local = source/'asm'/name
        if local.exists() and local.read_bytes() != asset.read_bytes():
            raise ValueError('Native kit source differs from shared source: '+name)
        shutil.copyfile(asset,out/name)
        input_names.append(name)
    high = out/'CAMLF91h.asm'
    high.write_bytes(high.read_bytes().replace(
        b'ifdef KIT\r\n' + KIT_INCLUDE.rstrip(b'\r\n') + b'\r\nendif ; KIT',
        KIT_INCLUDE.rstrip(b'\r\n')))
    original_link = (Path(__file__).parent/'poll.linkcmd').read_bytes()
    for name in ('console.inc','poll_bsp.asm'):
        shutil.copyfile(Path(__file__).parent/name,out/name)
    input_names.extend(('console.inc','poll_bsp.asm'))
    env = dict(os.environ,WINEPREFIX=str(args.wine_prefix.resolve()),WINEDEBUG='-all')
    args.wine_prefix.mkdir(parents=True,exist_ok=True)
    subprocess.run(['wineserver','-p60'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    log=[]
    def run(exe,*options):
        command=['wine',str(zds/'bin'/exe),*options]
        with (out/'tool.log').open('wb') as f:
            p=subprocess.run(command,cwd=out,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=60)
        text=(out/'tool.log').read_text(errors='replace')
        log.append(' '.join(command)+'\n'+text)
        (out/'build.log').write_text('\n'.join(log))
        print(text,end='',flush=True)
        if p.returncode: raise RuntimeError(exe+' failed')
    modules=['CAMLF91d','CAMLF91e','CAMLF91h','CAMLF91t','cstartup',
             'init_params_f91','vectors24','zsldevinitdummy','poll_bsp']
    inc=';'.join(wine_path(p) for p in (out,zds/'include/zilog',zds/'include/std'))
    for module in modules:
        run('ez80asm.exe','-cpu:eZ80F91','-define:_DEBUG','-define:FLASHED=0',
            '-include:'+inc,'-list',*(['-debug'] if getattr(args,'debug_info',False) else []),module+'.asm')
    link=original_link.decode().replace('\r\n','\n')
    if not getattr(args,'debug_info',False):
        link=link.replace('-FORMAT=OMF695,INTEL32','-FORMAT=INTEL32')
    link += '\nDEFINE __cstartup = 1\n"camel" = '+', '.join('"'+m+'.obj"' for m in modules)
    link += ', "'+wine_path(zds/'lib/std/chelpD.lib')+'"\n'
    (out/'camel.linkcmd').write_text(link)
    run('eZ80link.exe','@camel.linkcmd')
    subprocess.run([sys.executable,str(ROOT/'scripts/ihex_to_bin.py'),str(out/'camel.hex'),str(out/'camel.bin')],check=True)
    symbols = {}
    text = (out/'camel.map').read_text()
    for name in ('ENTRY','BYE','user0','defuser','__init','COLD'):
        match = re.search(r'^'+re.escape(name)+r'\s+[CD]:([0-9A-F]+)\b',text,re.MULTILINE)
        if not match: raise ValueError('Missing symbol '+name)
        symbols[name] = int(match[1],16)
    metadata={'symbols':symbols,'upstream_commit':COMMIT,'board':'ez80f91-freertos,ram-boot=on',
              'binary_sha256':hashlib.sha256((out/'camel.bin').read_bytes()).hexdigest(),
              'sources':{name:hashlib.sha256((out/name).read_bytes()).hexdigest()
                         for name in sorted(set(input_names))},
              'note':'Pinned core with reviewed 24-bit fixes; Debug memory/clock, explicit C startup and polling console BSP.'}
    (out/'camel.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(out/'camel.bin')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--debug-info',action='store_true',help='Also emit OMF695 and source line information for ZDS II')
    p.add_argument('--source',type=Path,default=ROOT/'subprojects/CAMELF91_24')
    p.add_argument('--zds',type=Path,required=True)
    p.add_argument('--out',type=Path,default=ROOT/'build/camelf91')
    p.add_argument('--wine-prefix',type=Path,default=Path('/tmp/qemuez80f91-zds-wine'))
    build(p.parse_args())
