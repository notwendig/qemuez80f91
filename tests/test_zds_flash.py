#!/usr/bin/env python3
"""Original ZDS EthernetSC DLL: erase/program/verify internal and AMD flash."""
import argparse
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def win(path):
    return 'Z:' + str(path.resolve()).replace('/', '\\')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu', type=Path, default=Path('/tmp/qemuez80f91-build-baseline/qemu-system-ez80'))
    parser.add_argument('--zds', type=Path, default=ROOT.parent / 'ZDSII_eZ80Acclaim!_5.3.5')
    parser.add_argument('--sdk', type=Path, default=ROOT.parent / 'NexusSDK_1.1')
    parser.add_argument('--wine-prefix', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='ez80-zds-flash-') as directory:
        work = Path(directory)
        exe = work / 'flash.exe'
        subprocess.run(['i686-w64-mingw32-gcc', '-Wall', '-Wextra', '-fpack-struct=4',
                        '-I' + str(args.sdk / 'include'), str(ROOT / 'tests/zds_nexus/flash.c'),
                        '-o', str(exe)], check=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        with (work / 'qemu.log').open('w+') as log:
            vm = subprocess.Popen([str(args.qemu.resolve()), '-M', 'ez80f91-minimal',
                f'--dbgport={port}', '-S', '-display', 'none', '-monitor', 'none',
                '-serial', 'none', '-nic', 'none', '-qmp', 'stdio'], cwd=work,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)

            def response():
                if not select.select([vm.stdout], [], [], 10)[0]:
                    raise AssertionError('QMP timeout')
                return json.loads(vm.stdout.readline())

            def command(name):
                vm.stdin.write(json.dumps({'execute': name}) + '\n')
                vm.stdin.flush()
                while True:
                    data = response()
                    if 'event' not in data:
                        assert 'return' in data, data
                        return data

            try:
                assert 'QMP' in response()
                command('qmp_capabilities')
                deadline = time.monotonic() + 10
                while True:
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=.1):
                            break
                    except OSError:
                        assert vm.poll() is None and time.monotonic() < deadline
                        time.sleep(.05)
                env = dict(os.environ, WINEDEBUG='-all')
                if args.wine_prefix:
                    env['WINEPREFIX'] = str(args.wine_prefix.resolve())
                result = subprocess.run(['wine', str(exe),
                    win(args.zds / 'bin/nxEz80EthernetSC.dll'),
                    win(args.zds / 'config/eZ80F91algo.ini'), str(port)],
                    env=env, capture_output=True, text=True, timeout=60)
                print(result.stdout, end='', flush=True)
                assert result.returncode == 0, result.stderr
                assert 'Warning:' not in result.stdout, result.stdout
                command('quit')
                vm.wait(timeout=10)
                assert vm.returncode == 0
            finally:
                if vm.poll() is None:
                    vm.terminate()
                    vm.wait(timeout=10)
                log.seek(0)
                errors = log.read()
                assert 'DTL failed' not in errors, errors
        expected = bytearray((i * 37 + (i >> 8)) & 255 for i in range(10240))
        expected[2048:6144] = b'\xff' * 4096
        internal = work / f'ez80f91_0.{port}'
        assert internal.read_bytes() == expected + b'\xff' * (256 * 1024 - len(expected))
        external = work / f'ez80f91_100000.{port}'
        pattern = bytes((i * 13 + 7) & 255 for i in range(512))
        assert external.read_bytes() == pattern + b'\xff' * (1024 * 1024 - len(pattern))
        print('PASS: native --dbgport, original ZDS DLL, internal/external flash files verified independently')


if __name__ == '__main__':
    main()
