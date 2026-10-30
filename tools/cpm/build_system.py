#!/usr/bin/env python3
"""Build CP/M system tracks with the installed ZDS II assembler under Wine."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from ihex_to_bin import convert


def main():
    source = ROOT / 'subprojects/FreeRTOS-eZ80f91/CPM'
    zds = Path.home() / '.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5/bin'
    env = dict(os.environ, WINEDEBUG='-all')
    with tempfile.TemporaryDirectory(prefix='cpm-system-') as temp:
        work = Path(temp)
        shutil.copytree(source / 'CPM22', work / 'CPM22')
        shutil.copyfile(source / 'CPM22.linkcmd', work / 'CPM22.linkcmd')
        for name in ('BOOT', 'CCP', 'BDOS', 'BIOS'):
            subprocess.run(['wine', str(zds / 'ez80asm.exe'),
                            '-define:_EZ80ACCLAIM!=1', '-define:CPM22',
                            '-quiet', '-cpu:eZ80F91', '-NOigcase',
                            '-include:CPM22', f'CPM22/{name}.ASM'],
                           cwd=work, env=env, check=True)
        subprocess.run(['wine', str(zds / 'eZ80link.exe'), '@CPM22.linkcmd'],
                       cwd=work, env=env, check=True)
        output = ROOT / 'images/cpm/system.bin'
        output.parent.mkdir(parents=True, exist_ok=True)
        size = convert(work / 'CPM22.hex', output, limit=26 * 2 * 128)
        print(f'{output}: {size} bytes')


if __name__ == '__main__':
    main()
