#!/usr/bin/env python3
"""Build the locally installed, proprietary ZTP TCPUDPDemo without redistributing it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
def win(path): return 'Z:'+str(path.resolve()).replace('/','\\')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zds',type=Path,default=Path.home()/'.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5')
    p.add_argument('--out',type=Path,default=ROOT/'build/ztp-tcpudp')
    p.add_argument('--wine-prefix',type=Path,default=Path('/tmp/qemuez80f91-zds-wine'))
    p.add_argument('--link-only',action='store_true')
    p.add_argument('--memory-profile',choices=['qemu','vendor'],default='qemu')
    p.add_argument('--filesystem',choices=['vendor','ram'],default='vendor',help='Use the vendor Flash volume or its built-in test RAM volume')
    a=p.parse_args(); zds=a.zds.resolve(); out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    sdk=zds/'ZTP2.5.1';demo=sdk/'ZTP/SamplePrograms/TCPUDPDemo'
    project=ET.parse(demo/'ZTP_TCPUDP_DEMO_eZ80F91_99C0879-AMD.zdsproj')
    tools=project.find('configurations/configuration/tools')
    def opt(tool,name):return tools.find(f"tool[@name='{tool}']/options/option[@name='{name}']").text or ''
    def resolve(text):return (demo/text.replace('\\','/')).resolve()
    sources=[resolve(f.text) for f in project.findall('files/file') if f.text.lower().endswith(('.c','.asm'))]
    includes=[resolve(x) for x in opt('Compiler','usrinc').split(';') if x]
    includes += [zds/'include/std',zds/'include/zilog']
    env=dict(os.environ,WINEPREFIX=str(a.wine_prefix.resolve()),WINEDEBUG='-all')
    logs=[]; compile_commands=[]
    def run(exe,*opts):
        if exe in ('ez80cc.exe','ez80asm.exe'):
            compile_commands.append([win(zds/'bin'/exe),*opts]);return
        cmd=['wine',exe if exe=='cmd.exe' else str(zds/'bin'/exe),*opts]
        r=subprocess.run(cmd,cwd=out,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=900)
        text=r.stdout.decode(errors='replace');logs.append(' '.join(cmd)+'\n'+text)
        (out/'build.log').write_text('\n'.join(logs))
        print(text,end='',flush=True)
        if r.returncode:raise RuntimeError(f'{exe} failed: {r.returncode}; see {out}/build.log')
    for source in ([] if a.link_only else sources):
        shutil.copy2(source,out/source.name)
        if a.filesystem=='ram' and source.name=='ZFS_Conf.c':
            target=out/source.name;text=target.read_text()
            for old,new in [('#define ZFS_USES_XFL','//#define ZFS_USES_XFL'),
                            ('//#define ZFS_USES_RAM','#define ZFS_USES_RAM')]:
                if text.count(old)!=1:raise ValueError('Unexpected ZFS configuration')
                text=text.replace(old,new)
            target.write_text(text)
        if source.suffix.lower()=='.c':
            run('ez80cc.exe','-cpu:eZ80F91',*[f'-define:{d}' for d in opt('Compiler','define').split(',')],
                '-asmsw:-cpu:eZ80F91','-nolink','-keepasm','-keeplst','-optsize','-promote','-reduceopt','-debug',
                '-stdinc:'+';'.join(map(win,includes)),source.name)
        else:
            run('ez80asm.exe','-cpu:eZ80F91','-define:_EZ80ACCLAIM!=1','-define:ZDS1=0',
                '-include:'+';'.join(map(win,includes)),'-list','-debug',source.name)
    if compile_commands:
        batch='@echo off\n'+'\n'.join(subprocess.list2cmdline(cmd)+'\nif errorlevel 1 exit /b 1' for cmd in compile_commands)+'\n'
        (out/'compile.bat').write_text(batch.replace('\n','\r\n'))
        run('cmd.exe','/c',win(out/'compile.bat'))
    template=(sdk/'ZTP/SamplePrograms/ZTPDemo/RAM/ZTPDemo_eZ80F91_99C0879-AMD_RAM.linkcmd').read_text()
    ctl=template[template.index('-FORMAT='):template.index('"Z:')]
    # Keep the vendor RAM startup values and original project libraries.
    if a.memory_profile=='qemu':
        params={'__FLASH_CTL_INIT_PARAM':'60','__CS1_LBR_INIT_PARAM':'00','__CS1_UBR_INIT_PARAM':'07',
                '__CS1_CTL_INIT_PARAM':'28','__CS2_LBR_INIT_PARAM':'80',
                '__CS2_UBR_INIT_PARAM':'BF','__CS2_CTL_INIT_PARAM':'28'}
        for name,value in params.items():
            ctl=re.sub(r'(DEFINE '+name+r' = )\$[0-9a-fA-F]+',r'\g<1>$'+value,ctl)
    objects=[zds/'lib/zilog'/n for n in ['vectors24.obj','init_params_f91.obj','cstartup.obj']]
    objects += [out/(s.stem+'.obj') for s in sources]
    objects += [resolve(x) for x in opt('Linker','objlibmods').split(',') if x]
    objects += [zds/'lib/std'/n for n in ['chelpD.lib','crtD.lib','crtSD.lib','nokernelD.lib','fpdumy.obj']]
    objects += [zds/'lib/zilog/zsldevinitdummy.obj']
    ctl+='"tcpudp" = '+(', '+chr(92)+'\n').join('"'+win(x)+'"' for x in objects)+'\n'
    (out/'tcpudp.linkcmd').write_text(ctl)
    run('eZ80link.exe','@tcpudp.linkcmd')
    subprocess.run(['python3',str(ROOT/'scripts/ihex_to_bin.py'),str(out/'tcpudp.hex'),str(out/'tcpudp.bin')],check=True)
    (out/'build.json').write_text(json.dumps({'project':str(demo),'memory_profile':a.memory_profile,'filesystem':a.filesystem,'sha256':hashlib.sha256((out/'tcpudp.bin').read_bytes()).hexdigest()},indent=2)+'\n')
if __name__=='__main__':main()
