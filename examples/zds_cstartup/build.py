#!/usr/bin/env python3
"""Build a real ZDS C probe using FreeRTOS-eZ80f91's unmodified cstartup.asm."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def wine_path(path):
    return 'Z:' + str(path.resolve()).replace('/', '\\')


def build(args):
    sources = Path(__file__).resolve().parent
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    zds = args.zds.resolve()
    startup = args.freertos.resolve() / 'EZ80F910300ZCOG/src/cstartup.asm'
    for filename in ('main.c', 'boot.asm'):
        shutil.copyfile(sources / filename, out / filename)
    shutil.copyfile(startup, out / 'cstartup.asm')
    env = os.environ.copy()
    env.update(WINEPREFIX=str(args.wine_prefix.resolve()), WINEDEBUG='-all')
    args.wine_prefix.mkdir(parents=True, exist_ok=True)
    logs = []

    def run(executable, *options):
        cmd = ['wine', str(zds / 'bin' / executable), *options]
        p = subprocess.run(cmd, cwd=out, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=60)
        text = p.stdout.decode(errors='replace')
        logs.append(' '.join(cmd) + '\n' + text)
        (out / 'build.log').write_text('\n'.join(logs))
        print(text, end='', flush=True)
        if p.returncode:
            raise RuntimeError(f'{executable} exited with status {p.returncode}')

    inc = ';'.join(wine_path(zds / 'include' / p) for p in ('std', 'zilog'))
    run('ez80cc.exe', '-cpu:eZ80F91', '-define:_EZ80F91',
        '-asmsw:-cpu:eZ80F91', '-nolink', '-keepasm', '-keeplst',
        '-optsize', '-stdinc:' + inc, 'main.c')
    for filename in ('boot.asm', 'cstartup.asm'):
        run('ez80asm.exe', '-cpu:eZ80F91', '-list', filename)
    lib = wine_path(zds / 'lib/std/chelpD.lib')
    (out / 'probe.linkcmd').write_text('''-FORMAT=INTEL32
-map -maxhexlen=64 -quiet -warnoverlap -xref -unresolved=fatal
RANGE ROM $000000 : $06AFFF
RANGE RAM $06B000 : $07FFFF
RANGE EXTIO $000000 : $00FFFF
RANGE INTIO $000000 : $0000FF
ORDER .RESET,.STARTUP,CODE,DATA
COPY DATA ROM
DEFINE __low_romdata = copy base of DATA
DEFINE __low_data = base of DATA
DEFINE __len_data = length of DATA
DEFINE __low_bss = base of BSS
DEFINE __len_bss = length of BSS
DEFINE __low_romcode = copy base of CODE
DEFINE __low_code = base of CODE
DEFINE __len_code = length of CODE
DEFINE __copy_code_to_ram = 0
"probe" = "boot.obj", "cstartup.obj", "main.obj", "''' + lib + '"\n')
    run('eZ80link.exe', '@probe.linkcmd')
    # The converter is part of the emulator project, not ZDS.
    converter = sources.parents[1] / 'scripts/ihex_to_bin.py'
    subprocess.run([sys.executable, str(converter), str(out / 'probe.hex'),
                    str(out / 'probe.bin')], check=True)
    text = (out / 'probe.map').read_text()
    names = ('_main', '_bss_probe', '_data_probe', '_result',
             '__c_startup', '__frameset')
    symbols = {}
    for name in names:
        match = re.search(r'^' + re.escape(name) + r'\s+[CD]:([0-9A-F]+)\b',
                          text, re.MULTILINE)
        if not match:
            raise ValueError(f'linker map has no {name}')
        symbols[name] = int(match[1], 16)
    commit = subprocess.run(['git', '-C', str(args.freertos), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True)
    metadata = {
        'freertos_commit': commit.stdout.strip() if commit.returncode == 0 else None,
        'startup_sha256': hashlib.sha256(startup.read_bytes()).hexdigest(),
        'binary_sha256': hashlib.sha256((out / 'probe.bin').read_bytes()).hexdigest(),
        'symbols': symbols,
        'board': 'ez80f91-freertos,ram-boot=on',
        'expected_result': 0x123456,
        'expected_uart_hex': '43',
        'note': 'Original C startup plus ZDS C probe; no FreeRTOS scheduler yet.',
    }
    (out / 'probe.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(out / 'probe.bin')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zds', type=Path, required=True)
    p.add_argument('--freertos', type=Path, required=True)
    p.add_argument('--out', type=Path, default=Path('build/zds-probe'))
    p.add_argument('--wine-prefix', type=Path,
                   default=Path('/tmp/qemuez80f91-zds-wine'))
    build(p.parse_args())
