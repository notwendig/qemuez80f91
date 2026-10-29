#!/usr/bin/env python3
"""Assemble original FreeRTOS-eZ80f91 vectors24.asm with a Timer0 probe."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def build(args):
    sources = Path(__file__).resolve().parent
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    vectors = args.freertos.resolve() / 'EZ80F910300ZCOG/src/vectors24.asm'
    shutil.copyfile(vectors, out / 'vectors24.asm')
    shutil.copyfile(sources / 'hooks.asm', out / 'hooks.asm')
    args.wine_prefix.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(WINEPREFIX=str(args.wine_prefix.resolve()), WINEDEBUG='-all')
    log = []

    def run(tool, *options):
        cmd = ['wine', str(args.zds.resolve() / 'bin' / tool), *options]
        p = subprocess.run(cmd, cwd=out, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=60)
        text = p.stdout.decode(errors='replace')
        log.append(' '.join(cmd) + '\n' + text)
        (out / 'build.log').write_text('\n'.join(log))
        print(text, end='', flush=True)
        if p.returncode:
            raise RuntimeError(f'{tool}: exit {p.returncode}')

    for filename in ('vectors24.asm', 'hooks.asm'):
        run('ez80asm.exe', '-cpu:eZ80F91', '-list', filename)
    (out / 'probe.linkcmd').write_text('''-FORMAT=INTEL32
-map -maxhexlen=64 -quiet -warnoverlap -xref -unresolved=fatal
RANGE ROM $000000 : $06AFFF
RANGE RAM $06B000 : $07FFFF
RANGE EXTIO $000000 : $00FFFF
RANGE INTIO $000000 : $0000FF
ORDER .RESET,.IVECTS,.STARTUP,CODE,DATA
"probe" = "vectors24.obj", "hooks.obj"
''')
    run('eZ80link.exe', '@probe.linkcmd')
    converter = sources.parents[1] / 'scripts/ihex_to_bin.py'
    subprocess.run([sys.executable, str(converter), str(out / 'probe.hex'),
                    str(out / 'probe.bin')], check=True)
    symbols = {}
    text = (out / 'probe.map').read_text()
    for name in ('_ticks', '_done', '__init', '__vector_table',
                 '__init_default_vectors', '_set_vector'):
        m = re.search(r'^' + re.escape(name) + r'\s+[CD]:([0-9A-F]+)\b',
                      text, re.MULTILINE)
        if not m:
            raise ValueError(f'missing linker symbol {name}')
        symbols[name] = int(m[1], 16)
    commit = subprocess.run(['git', '-C', str(args.freertos), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True)
    metadata = {
        'symbols': symbols,
        'freertos_commit': commit.stdout.strip() if commit.returncode == 0 else None,
        'vectors_sha256': hashlib.sha256(vectors.read_bytes()).hexdigest(),
        'binary_sha256': hashlib.sha256((out / 'probe.bin').read_bytes()).hexdigest(),
        'board': 'ez80f91-freertos,ram-boot=on',
        'expected_uart_hex': '545454',
        'note': 'Original vectors24.asm, custom Timer0 handler; no FreeRTOS scheduler.',
    }
    (out / 'probe.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(out / 'probe.bin')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zds', type=Path, required=True)
    p.add_argument('--freertos', type=Path, required=True)
    p.add_argument('--out', type=Path, default=Path('build/timer0-vectors'))
    p.add_argument('--wine-prefix', type=Path,
                   default=Path('/tmp/qemuez80f91-zds-wine'))
    build(p.parse_args())
