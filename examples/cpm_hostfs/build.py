#!/usr/bin/env python3
"""Build CP/M 2.2 with native 8-bit console/FCB/FDC ports, without FreeRTOS traps."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from ihex_to_bin import convert


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zds', type=Path, default=Path.home() / '.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5')
    p.add_argument('--wine-prefix', type=Path, default=Path('/tmp/ez80-flash-debug-wine'))
    p.add_argument('--out', type=Path, default=ROOT / 'build/cpm-hostfs')
    args = p.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    for source in (ROOT / 'subprojects/FreeRTOS-eZ80f91/CPM/CPM22').iterdir():
        if source.suffix.upper() in ('.ASM', '.INC'):
            shutil.copyfile(source, out / source.name)
    env = dict(os.environ, WINEPREFIX=str(args.wine_prefix.resolve()), WINEDEBUG='-all')
    logs = []
    def run(exe, *options):
        result = subprocess.run(['wine', str(args.zds.resolve() / 'bin' / exe), *options],
                                cwd=out, env=env, capture_output=True, text=True, timeout=60)
        logs.append(result.stdout + result.stderr)
        (out / 'build.log').write_text('\n'.join(logs))
        assert result.returncode == 0, logs[-1]
    for name in ('BOOT', 'CCP', 'BDOS', 'BIOS'):
        run('ez80asm.exe', '-cpu:eZ80F91', '-define:CPM22',
            '-NOigcase', '-list', name + '.ASM')
    (out / 'cpm.linkcmd').write_text('''-FORMAT=INTEL32
-map -quiet -warning=fatal -unresolved=fatal
RANGE ROM $000000 : $07FFFF
RANGE RAM $000000 : $00FFFF
RANGE EXTIO $0000 : $FFFF
RANGE INTIO $0000 : $00FF
DEFINE CCPBASE=$E400
DEFINE BDOSBASE=$EC00
DEFINE BIOSBASE=$FA00
DEFINE ROMTOP=$FFFF
COPY _BOOT ROM AT $0000
COPY _CCP ROM AT $E400
COPY _BDOS ROM AT $EC00
COPY _BIOS ROM AT $FA00
"cpm" = "BOOT.obj", "CCP.obj", "BDOS.obj", "BIOS.obj"
''')
    run('eZ80link.exe', '@cpm.linkcmd')
    size = convert(out / 'cpm.hex', out / 'cpm.bin', 0x10000)
    (out / 'cpm.json').write_text(json.dumps({
        'binary_sha256': hashlib.sha256((out / 'cpm.bin').read_bytes()).hexdigest(),
        'sources': {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                    for name in ('BOOT.ASM', 'CCP.ASM', 'BDOS.ASM', 'BIOS.ASM', 'CPM.INC', 'HWC.INC')},
        'board': 'ez80f91-freertos,ram-boot=on',
        'console_ports': [0x8c, 0x8d], 'filesystem_ports': [0x8e, 0x8f],
        'fdc_ports': [0x18, 0x1f],
    }, indent=2) + '\n')
    print(f'{out / "cpm.bin"}: {size} bytes; native BIOS/BDOS ports')


if __name__ == '__main__':
    main()
