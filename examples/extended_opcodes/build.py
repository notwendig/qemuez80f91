#!/usr/bin/env python3
"""Check QEMU test encodings independently with the installed ZDS assembler."""
import argparse
from pathlib import Path
import os
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--zds',type=Path,default=Path.home()/'.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5')
parser.add_argument('--out',type=Path,default=ROOT/'build/extended-opcodes')
parser.add_argument('--wine-prefix',type=Path,default=Path('/tmp/qemuez80f91-zds-wine'))
args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
source=Path(__file__).with_name('opcodes.asm');shutil.copyfile(source,args.out/'opcodes.asm')
env=dict(os.environ,WINEPREFIX=str(args.wine_prefix.resolve()),WINEDEBUG='-all')
result=subprocess.run(['wine',str(args.zds.resolve()/'bin/ez80asm.exe'),'-cpu:eZ80F91','-list','opcodes.asm'],
                      cwd=args.out,env=env,capture_output=True,text=True,timeout=60)
(args.out/'assembler.log').write_text(result.stdout+result.stderr)
if result.returncode:raise RuntimeError((result.stdout+result.stderr).strip())
listing=(args.out/'opcodes.lst').read_text()
expected=dict(re.findall(r'^(probe_\d+):.*; bytes=([0-9A-F]+)',source.read_text(),re.MULTILINE))
found=dict((name,code) for code,name in re.findall(r'^[0-9A-F]{6}\s+([0-9A-F]+)\s+A\s+\d+\s+(probe_\d+):',listing,re.MULTILINE))
for name,code in expected.items():assert found.get(name)==code,(name,code,found.get(name))
print(f'PASS: {len(expected)} eZ80F91 opcode encodings confirmed by ZDS II')
