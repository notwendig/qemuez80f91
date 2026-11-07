#!/usr/bin/env python3
"""Load a 260-KiB ROM through ZDS across internal/external flash, then cold boot."""
import argparse
import json
import os
from pathlib import Path
import re
import select
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ihex_to_bin import convert


def win(path):
    return 'Z:' + str(path.resolve()).replace('/', '\\')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu', type=Path, default=ROOT / 'install/bin/qemu-system-ez80')
    parser.add_argument('--zds', type=Path, default=ROOT.parent / 'ZDSII_eZ80Acclaim!_5.3.5')
    parser.add_argument('--wine-prefix', type=Path, default=Path('/tmp/ez80-flash-debug-wine'))
    parser.add_argument('--out', type=Path, default=ROOT / 'build/zds-flash-boundary')
    args = parser.parse_args()
    work = args.out.resolve()
    work.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, WINEPREFIX=str(args.wine_prefix.resolve()), WINEDEBUG='-all')
    # Dense data makes this a real >256-KiB download, including a data block
    # crossing the chip boundary, and an actual call into external flash.
    lines = ['DEFINE .RESET,SPACE=ROM,ORG=0', 'SEGMENT .RESET',
             'DB 05Bh,0C3h,5,0,0', '.ASSUME ADL=1', 'DI',
             'LD SP,0B7FFF0h', 'LD A,4', 'OUT0 (0A8h),A',
             'LD A,013h', 'OUT0 (0A9h),A', 'LD A,0A8h', 'OUT0 (0AAh),A',
             'LD A,0B7h', 'OUT0 (0B5h),A', 'LD A,080h', 'OUT0 (0B4h),A',
             'CALL external_code', 'LD A,0A5h', 'LD (0B7FF01h),A', 'HALT',
             'DEFINE FILL,SPACE=ROM,ORG=0100h', 'SEGMENT FILL']
    for start in range(0x100, 0x40020, 64):
        count = min(64, 0x40020 - start)
        lines.append('DB ' + ','.join(f'0{((start+i)*37+(start+i)//256)&255:02X}h'
                                    for i in range(count)))
    lines += ['DEFINE EXTCODE,SPACE=ROM,ORG=040020h', 'SEGMENT EXTCODE',
              'external_code:', 'LD HL,03FFF0h', 'LD B,32', 'XOR A',
              'sum_loop:', 'ADD A,(HL)', 'INC HL', 'DJNZ sum_loop',
              'LD (0B7FF00h),A', 'RET',
              'DEFINE TAIL,SPACE=ROM,ORG=040100h', 'SEGMENT TAIL']
    for start in range(0x40100, 0x41000, 64):
        lines.append('DB ' + ','.join(f'0{((start+i)*13+7)&255:02X}h' for i in range(64)))
    (work / 'probe.asm').write_text('\n'.join(lines + ['END']) + '\n')
    (work / 'probe.linkcmd').write_text('''-FORMAT=OMF695,INTEL32
-map -maxhexlen=64 -quiet -warnoverlap -xref -unresolved=fatal -warning=fatal
RANGE ROM $000000 : $03FFFF, $040000 : $13FFFF
RANGE RAM $B7E000 : $B7FFFF
RANGE EXTIO $000000 : $00FFFF
RANGE INTIO $000000 : $0000FF
"probe" = "probe.obj"
''')
    for exe, options in [('ez80asm.exe', ['-cpu:eZ80F91', '-debug', '-list', 'probe.asm']),
                         ('eZ80link.exe', ['@probe.linkcmd'])]:
        result = subprocess.run(['wine', str(args.zds.resolve() / 'bin' / exe), *options],
                                cwd=work, env=env, capture_output=True, text=True, timeout=60)
        (work / (exe + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
    assert convert(work / 'probe.hex', work / 'probe.bin', 0x140000) == 0x41000
    expected = (work / 'probe.bin').read_bytes()
    expected_sum = sum(expected[0x3fff0:0x40010]) & 255
    source = ROOT / 'subprojects/FreeRTOS-eZ80f91'
    project = (source / 'EZ80F910300ZCOG.zdsproj').read_bytes()
    project = re.sub(rb'<files>.*?</files>', b'<files></files>', project, flags=re.S)
    project = re.sub(rb'configuration="[^"]+"', b'configuration="Release"', project, count=1)
    (work / 'EZ80F910300ZCOG.zdsproj').write_bytes(project)
    shutil.copyfile(source / 'eZ80F91_99C0942_Flash.ztgt', work / 'eZ80F91_99C0942_Flash.ztgt')
    (work / 'Release').mkdir(exist_ok=True)
    shutil.copyfile(work / 'probe.lod', work / 'Release/EZ80F910300ZCOG.lod')
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1', 0))
        port = reserve.getsockname()[1]

    def start_vm(phase):
        log = (work / (phase + '-qemu.log')).open('w')
        vm = subprocess.Popen([str(args.qemu.resolve()), '-M', 'ez80f91-minimal,cs3=none',
                               '-S', '-display', 'none', '-monitor', 'none', '-serial', 'none',
                               '-nic', 'none', f'--dbgport={port}', '-qmp', 'stdio'],
                              cwd=work, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                              bufsize=0)
        def read():
            assert select.select([vm.stdout], [], [], 10)[0], 'QMP timeout'
            return json.loads(vm.stdout.readline())
        def command(name, arguments=None):
            message = {'execute': name}
            if arguments is not None:
                message['arguments'] = arguments
            vm.stdin.write(json.dumps(message).encode() + b'\n')
            vm.stdin.flush()
            while True:
                reply = read()
                if 'event' not in reply:
                    assert 'return' in reply, reply
                    return reply['return']
        assert 'QMP' in read()
        command('qmp_capabilities')
        return vm, command, log

    def verify_run(command):
        command('cont')
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            registers = command('human-monitor-command', {'command-line': 'info registers'})
            if 'HALTED=1' in registers:
                break
            time.sleep(.05)
        else:
            raise AssertionError(registers)
        command('stop')
        result = work / 'result.bin'
        command('pmemsave', {'val': 0xb7ff00, 'size': 2, 'filename': str(result)})
        assert result.read_bytes() == bytes([expected_sum, 0xa5]), result.read_bytes().hex()

    vm, command, qlog = start_vm('load')
    ide = None
    try:
        session = work / 'session.log'
        session.unlink(missing_ok=True)
        script = work / 'load.cmd'
        script.write_text('\n'.join([f'cd "{win(work)}"', f'log "{win(session)}"', 'log on',
            'open project "EZ80F910300ZCOG.zdsproj"', 'debugtool set "EthernetSmartCable"',
            'debugtool set "ipAddress" "127.0.0.1"', f'debugtool set "ethernetPort" "{port}"',
            'reset', 'print "BOUNDARY_LOAD_FINISHED PC=%x" reg PC', 'log off', 'quit']) + '\n')
        with (work / 'ide.log').open('w') as ilog:
            ide = subprocess.Popen(['wine', str(args.zds.resolve() / 'bin/Zds2Ide.exe'),
                                    '@' + win(script)], cwd=work, env=env, stdout=ilog, stderr=ilog)
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline and ide.poll() is None:
                if session.exists() and 'BOUNDARY_LOAD_FINISHED' in session.read_text(errors='replace'):
                    break
                time.sleep(.5)
            text = session.read_text(errors='replace')
            print(text[-3000:], flush=True)
            assert 'successful.' in text and '[ERROR]' not in text, text
        command('pmemsave', {'val': 0, 'size': len(expected), 'filename': str(work / 'readback.bin')})
        assert (work / 'readback.bin').read_bytes() == expected, 'flash download mismatch'
        verify_run(command)
        print('PASS: ZDS loaded 260 KiB; full flash readback, boundary data and external call/return', flush=True)
    finally:
        if ide is not None and ide.poll() is None:
            ide.terminate()
            ide.wait(timeout=10)
        command('quit')
        vm.wait(timeout=10)
        qlog.close()
    vm, command, qlog = start_vm('cold')
    try:
        verify_run(command)
        print('PASS: cold boot from persisted internal/external flash crosses 03FFFF -> 040000', flush=True)
    finally:
        command('quit')
        vm.wait(timeout=10)
        qlog.close()


if __name__ == '__main__':
    main()
