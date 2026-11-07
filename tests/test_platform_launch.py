#!/usr/bin/env python3
"""Exercise native Qt launcher with real QEMU, private disks and saved flash."""
import argparse
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools', type=Path, default=ROOT / 'build/platform-tools/tools/qt/ez80-platform')
    parser.add_argument('--qemu', type=Path, default=ROOT / 'build/ez80/qemu-system-ez80')
    parser.add_argument('--bridge', help='Also test a paused Qt/kit session on an existing bridge')
    args = parser.parse_args()
    native, qemu = args.tools.resolve(), args.qemu.resolve()
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    with tempfile.TemporaryDirectory(prefix='ez80-qt-launch-') as temp:
        work = Path(temp)
        disks = work / 'disks'
        disks.mkdir()
        disk = disks / 'A.img'
        disk.write_bytes((b'keep saved guest disk\0' * 13000)[:256256])
        disk_before = disk.read_bytes()
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        command = [str(native), 'start', '--qemu', str(qemu), '--bridge', 'none',
                   '--port', str(port), '--dev', str(disks),
                   '--bios', str(ROOT / 'examples/hello_uart0.bin')]
        runtime = Path('/tmp') / f'ez80f91-{os.getuid()}'
        uart = runtime / f'{port}.uart.log'
        for options in (['--port', '0'], ['--port', '65536'], ['--hostname', '-invalid'],
                        ['--wd2797a', '0xfef9'], ['--wd2797a', '0xff4b']):
            result = subprocess.run([*command, '--headless', *options], cwd=work, env=env,
                                    capture_output=True, timeout=10)
            assert result.returncode == 2, (options, result.stderr)
        for headless in (True, False):
            result = subprocess.run([*command, '--run', '--seconds', '.4',
                                     *(['--headless'] if headless else ['--kit'])],
                                    cwd=work, env=env, capture_output=True, timeout=20)
            assert result.returncode == 0, result.stderr.decode()
            assert b'Hello eZ80F91' in uart.read_bytes(), (result.stdout, result.stderr, uart.read_bytes())
            assert disk.read_bytes() == disk_before
            assert not (runtime / f'{port}.qmp').exists()
            assert not (runtime / f'{port}.uart.sock').exists()
        if args.bridge:
            bridged = subprocess.run([*command, '--bridge', args.bridge, '--kit', '--seconds', '.1'],
                                     cwd=work, env=env, stdin=subprocess.DEVNULL,
                                     capture_output=True, timeout=45)
            assert bridged.returncode == 0, bridged.stderr.decode()
            assert b'CPU wartet auf ZDS II.' in bridged.stderr, bridged.stderr
            assert disk.read_bytes() == disk_before
            print('PASS: paused Qt/kit session on bridge', args.bridge, 'with', qemu)
        saved = work / f'ez80f91_0.{port}'
        assert saved.exists(), 'flash not persisted'
        flash_before = saved.read_bytes()
        log = (work / 'paused.log').open('wb')
        child = subprocess.Popen([*command, '--headless'], cwd=work, env=env,
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 10
            while not (runtime / f'{port}.qmp').exists():
                assert child.poll() is None, (work / 'paused.log').read_text()
                assert time.monotonic() < deadline, 'QMP startup timeout'
                time.sleep(.03)
            duplicate = subprocess.run([*command, '--headless', '--seconds', '.1'], cwd=work,
                                       env=env, capture_output=True, timeout=10)
            assert duplicate.returncode == 1 and b'bereits' in duplicate.stderr, duplicate.stderr
            child.send_signal(signal.SIGTERM)
            assert child.wait(timeout=15) == 0
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=15)
            log.close()
        assert saved.read_bytes() == flash_before, 'paused session changed flash'
        assert disk.read_bytes() == disk_before
        result = subprocess.run([*command, '--headless', '--seconds', '.1'], cwd=work,
                                env=env, capture_output=True, timeout=15)
        assert result.returncode == 0, result.stderr
        assert not (runtime / f'{port}.qmp').exists()
        # The QEMU child must retain the lock if its launcher dies abruptly.
        log = (work / 'orphan.log').open('wb')
        child = subprocess.Popen([*command, '--headless'], cwd=work, env=env,
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        qemu_pid = None
        try:
            deadline = time.monotonic() + 10
            while not (runtime / f'{port}.qmp').exists():
                assert child.poll() is None
                assert time.monotonic() < deadline
                time.sleep(.03)
            descendants = Path(f'/proc/{child.pid}/task/{child.pid}/children').read_text().split()
            assert len(descendants) == 1, descendants
            qemu_pid = int(descendants[0])
            child.kill()
            child.wait(timeout=5)
            duplicate = subprocess.run([*command, '--headless', '--seconds', '.1'], cwd=work,
                                       env=env, capture_output=True, timeout=10)
            assert duplicate.returncode == 1 and b'Instanz l' in duplicate.stderr, duplicate.stderr
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=15)
            if qemu_pid is not None:
                try:
                    os.kill(qemu_pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            log.close()
        # Wait for the orphaned test QEMU to save flash and release its lock.
        deadline = time.monotonic() + 10
        while True:
            result = subprocess.run([*command, '--headless', '--seconds', '.1'], cwd=work,
                                    env=env, capture_output=True, timeout=15)
            if result.returncode == 0:
                break
            assert time.monotonic() < deadline, result.stderr
            time.sleep(.05)
        assert disk.read_bytes() == disk_before
        assert saved.read_bytes() == flash_before
        serial = subprocess.run([str(native), 'zds-launch', '--qemu', str(qemu),
                                 '--bios', str(ROOT / 'examples/hello_uart0.bin'),
                                 '--port', str(port), '--serial', 'stdio', '--run', '--seconds', '.2'],
                                cwd=work, env=env, input=b'', capture_output=True, timeout=15)
        assert serial.returncode == 0, serial.stderr
        assert b'Hello eZ80F91' in serial.stdout, (serial.stdout, serial.stderr)
    print('PASS: Qt UART and kit launch, validation, duplicate locking, SIGTERM, flash/disk preservation and cleanup')


if __name__ == '__main__':
    main()
