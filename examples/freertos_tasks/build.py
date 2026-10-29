#!/usr/bin/env python3
"""Build real FreeRTOS preemption, blocking/yield, and tick rollover probes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def wine_path(path):
    return 'Z:' + str(path.resolve()).replace('/', '\\')


def build(args):
    sources = Path(__file__).resolve().parent
    scenario = getattr(args, 'scenario', 'preempt')
    board = scenario in ('board', 'pll')
    variant = sources / ('board' if board else 'blocking') if scenario != 'preempt' else sources
    default_out = 'freertos-tasks' if scenario == 'preempt' else 'freertos-' + scenario
    out = (args.out or Path('build') / default_out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    zds = args.zds.resolve()
    args.kernel = args.kernel.resolve()
    kernel_commit = subprocess.check_output(
        ['git', '-C', str(args.kernel), 'rev-parse', 'HEAD'], text=True).strip()
    if kernel_commit != '0264280230aa6a828247b5f05bf57e33f1994581':
        raise ValueError('Kernel checkout must be V10.6.1')
    startup = args.freertos.resolve() / 'EZ80F910300ZCOG/src/cstartup.asm'
    for filename in ('main.c', 'boot.asm', 'FreeRTOSConfig.h'):
        shutil.copyfile(variant / filename, out / filename)
    initial_tick = 0xfffffc if scenario == 'wrap' else 0
    if scenario == 'wrap':
        config = out / 'FreeRTOSConfig.h'
        config.write_text(config.read_text().replace(
            '#endif', '#define configINITIAL_TICK_COUNT 0xfffffcU\n#endif'))
    shutil.copyfile(startup, out / 'cstartup.asm')
    assembly = ['boot.asm', 'cstartup.asm', 'vectors24.asm', 'llport.asm']
    if board:
        assembly.append('init_params_f91.asm')
    for name in assembly[2:]:
        shutil.copyfile(startup.parent / name, out / name)
    for name in ('portmacro.h', 'stdint.h'):
        shutil.copyfile(startup.parents[1] / 'inc' / name, out / name)
    for name in ('tasks.c', 'list.c'):
        (out / name).write_bytes(subprocess.check_output(
            ['git', '-C', str(args.kernel), 'show', 'HEAD:' + name]))
    patch = args.freertos.resolve() / 'patches/kernel-V10.6.1.patch'
    with tempfile.TemporaryDirectory(prefix='ez80-kernel-patch-') as td:
        staging = Path(td)
        shutil.copyfile(out / 'tasks.c', staging / 'tasks.c')
        subprocess.run(['git', 'apply', '--include=tasks.c', str(patch)],
                       cwd=staging, check=True)
        shutil.copyfile(staging / 'tasks.c', out / 'tasks.c')
    env = os.environ.copy()
    env.update(WINEPREFIX=str(args.wine_prefix.resolve()), WINEDEBUG='-all')
    args.wine_prefix.mkdir(parents=True, exist_ok=True)
    subprocess.run(['wineserver', '-p60'], env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    logs = []

    def run(executable, *options):
        cmd = ['wine', str(zds / 'bin' / executable), *options]
        with (out / 'tool.log').open('wb') as tool_log:
            p = subprocess.run(cmd, cwd=out, env=env, stdout=tool_log,
                               stderr=subprocess.STDOUT, timeout=60)
        text = (out / 'tool.log').read_text(errors='replace')
        logs.append(' '.join(cmd) + '\n' + text)
        (out / 'build.log').write_text('\n'.join(logs))
        print(text, end='', flush=True)
        if p.returncode:
            raise RuntimeError(f'{executable} exited with status {p.returncode}')

    inc = ';'.join(wine_path(zds / 'include' / p) for p in ('std', 'zilog'))
    for name in ('main.c', 'tasks.c', 'list.c'):
        run('ez80cc.exe', '-cpu:eZ80F91', '-define:_EZ80F91',
            '-asmsw:-cpu:eZ80F91', '-nolink', '-keepasm', '-keeplst',
            '-optsize', '-stdinc:' + inc,
            '-usrinc:' + wine_path(out) + ';' + wine_path(args.kernel / 'include'), name)
    for filename in assembly:
        run('ez80asm.exe', '-cpu:eZ80F91', '-include:' + wine_path(zds / 'include/zilog'), '-list', filename)
    lib = wine_path(zds / 'lib/std/chelpD.lib')
    linkcmd = '''-FORMAT=INTEL32
-map -maxhexlen=64 -quiet -warnoverlap -xref -unresolved=fatal
RANGE ROM $000000 : $06AFFF
RANGE RAM $06B000 : $BFFFFF
RANGE EXTIO $000000 : $00FFFF
RANGE INTIO $000000 : $0000FF
ORDER .RESET,.IVECTS,.STARTUP,CODE,DATA
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
"probe" = "boot.obj", "cstartup.obj", "main.obj", "tasks.obj", "list.obj", "vectors24.obj", "llport.obj", "''' + lib + '", "' + wine_path(zds / 'lib/std/crtD.lib') + '"\n'
    if board:
        # Memory/clock parameters from the original project's published map.
        values = {}
        published = (args.freertos / 'bin/EZ80F910300ZCOGd.map').read_text()
        for name, value in re.findall(
                r'^define\s+((?:__CS[0-3]_\w+|__RAM_\w+|__FLASH_\w+|__PLL_CTL0)_INIT_PARAM|_SYS_CLK_FREQ|_OSC_FREQ|_SYS_CLK_SRC|_OSC_FREQ_MULT)\s*=\s*(\$?[0-9a-f]+)\s*$',
                published, re.MULTILINE | re.IGNORECASE):
            values[name] = value
        if len(values) != 25:
            raise ValueError(f'Expected 25 published startup parameters, got {len(values)}')
        if scenario == 'pll':
            values.update(_OSC_FREQ='10000000', _SYS_CLK_SRC='1', _OSC_FREQ_MULT='5')
        parameters = ''.join(f'DEFINE {name} = {value}\n' for name, value in values.items())
        parameters += 'DEFINE __stack = $B90000\nDEFINE __cstartup = 1\n'
        linkcmd = linkcmd.replace('RANGE RAM $06B000 : $BFFFFF',
                                 'RANGE RAM $06B000 : $07FFFF, $B80000 : $B8FFFF')
        linkcmd = linkcmd.replace('\"probe\" =', parameters + '\"probe\" =')
        linkcmd = linkcmd.replace('\"boot.obj\",', '\"init_params_f91.obj\", \"boot.obj\",')
        linkcmd = linkcmd.rstrip() + ', \"' + wine_path(zds / 'lib/zilog/zsldevinitdummy.obj') + '\"\n'
    (out / 'probe.linkcmd').write_text(linkcmd)
    run('eZ80link.exe', '@probe.linkcmd')
    # The converter is part of the emulator project, not ZDS.
    converter = sources.parents[1] / 'scripts/ihex_to_bin.py'
    subprocess.run([sys.executable, str(converter), str(out / 'probe.hex'),
                    str(out / 'probe.bin')], check=True)
    text = (out / 'probe.map').read_text()
    names = ('_main', '_runs', '_failure', '_pxCurrentTCB', '_xTickCount', 'switch', '_firstTASK', '_tcbs', '_stacks', '_criticalcounter')
    if board:
        names += ('__init', '_InitSysClk', '_InitSysClkDone', '_init_sys_clk_pll',
                  '_startup_ports', '_startup_bss', '_startup_data', '_startup_ok', '_startup_sp')
    elif scenario != 'preempt':
        names += ('_event_count', '_events', '_event_ticks', '_idle_seen',
                  '_idle_entries', '_cooperative_done', '_done', '_final_tick',
                  '_interrupts_enabled')
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
        'kernel_commit': kernel_commit,
        'kernel_patch_sha256': hashlib.sha256(patch.read_bytes()).hexdigest(),
        'source_sha256': {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                          for name in ('tasks.c', 'list.c', 'vectors24.asm', 'llport.asm',
                                       'cstartup.asm', 'portmacro.h', 'stdint.h',
                                       'main.c', 'boot.asm', 'FreeRTOSConfig.h')},
        'expected_uart_hex': ('424142414241424121' if scenario in ('preempt', 'board', 'pll')
                              else b'BAbaD2456!'.hex()),
        'tcb_size': int(re.search(r'_tcbs:\s+DS\s+(\d+)',
                                  (out / 'main.src').read_text()).group(1)) // 3,
        'stack_words': 512,
        'note': 'FreeRTOS V10.6.1 with project patch; original vectors and llport, minimal application port.',
    }
    if board:
        metadata['source_sha256']['init_params_f91.asm'] = hashlib.sha256(
            (out / 'init_params_f91.asm').read_bytes()).hexdigest()
        metadata.update(scenario=scenario,
                        startup_parameters=values,
                        board='ez80f91-freertos,ram-boot=on,osc-frequency=' +
                              ('10000000' if scenario == 'pll' else '50000000'),
                        note='Original init_params_f91, vectors, C startup and ZDS peripheral-init dummy; two real kernel tasks.')
    elif scenario != 'preempt':
        metadata.update(scenario=scenario, initial_tick=initial_tick,
                        expected_event_offsets=[0, 0, 0, 0, 0, 2, 4, 5, 6, 6],
                        note='Original kernel/port: voluntary yield, critical nesting, delay/idle; optional tick rollover.')
    (out / 'probe.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(out / 'probe.bin')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scenario', choices=('preempt', 'blocking', 'wrap', 'board', 'pll'), default='preempt')
    p.add_argument('--kernel', type=Path, required=True)
    p.add_argument('--zds', type=Path, required=True)
    p.add_argument('--freertos', type=Path, required=True)
    p.add_argument('--out', type=Path, help='output directory (default: build/freertos-<scenario>)')
    p.add_argument('--wine-prefix', type=Path,
                   default=Path('/tmp/qemuez80f91-zds-wine'))
    build(p.parse_args())
