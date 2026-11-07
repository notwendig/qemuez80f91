#!/usr/bin/env python3
"""Verify persistent-flash deployment, rollback, live-QEMU protection and cold boot."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import flash_firmware as flash

qemu = Path(sys.argv[1]).resolve()
source = Path(sys.argv[2]).resolve()
with tempfile.TemporaryDirectory(prefix='vscodium-flash-') as temp:
    work = Path(temp)
    inputs = work / 'inputs'
    inputs.mkdir()
    manifest = json.loads(source.read_text())
    for image in manifest['images']:
        shutil.copyfile(source.parent / image['file'], inputs / image['file'])
    manifest_path = inputs / 'build.json'
    manifest_path.write_text(json.dumps(manifest))
    state = work / 'state'
    state.mkdir()
    sentinel = state / 'unrelated.txt'
    sentinel.write_text('KEEP')
    original = b'old firmware with user changes'
    (state / 'ez80f91_0.0').write_bytes(original)
    backup = flash.program(manifest_path, state, 0)
    assert (backup / 'ez80f91_0.0').read_bytes() == original
    snapshots = {}
    for image in manifest['images']:
        name = f'ez80f91_{image["base"]:X}.0'
        data = (state / name).read_bytes()
        assert len(data) == image['size'] + 4
        assert int.from_bytes(data[-4:], 'little') == zlib.crc32(data[:-4])
        assert hashlib.sha256(data[:-4]).hexdigest() == image['sha256']
        snapshots[name] = data
    # Invalid inputs must fail before touching live session state or flash.
    damaged = inputs / manifest['images'][0]['file']
    valid = damaged.read_bytes()
    damaged.write_bytes(valid[:-1])
    try:
        flash.program(manifest_path, state, 0)
        raise AssertionError('Truncated image was accepted')
    except ValueError:
        pass
    damaged.write_bytes(valid)
    assert all((state / name).read_bytes() == data for name, data in snapshots.items())
    # A failure replacing the second image rolls the first one back.
    changed = bytearray(valid)
    changed[1000] ^= 1
    damaged.write_bytes(changed)
    manifest['images'][0]['sha256'] = hashlib.sha256(changed).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    injected = [False]
    real_atomic = flash.atomic
    def fail_external(path, data):
        if path.name.startswith('ez80f91_40000.'):
            injected[0] = True
            raise OSError('injected write failure')
        real_atomic(path, data)
    with patch.object(flash, 'atomic', fail_external):
        try:
            flash.program(manifest_path, state, 0)
            raise AssertionError('Injected failure did not propagate')
        except OSError:
            pass
    assert injected[0], 'Rollback test did not reach the injected failure'
    assert all((state / name).read_bytes() == data for name, data in snapshots.items())
    damaged.write_bytes(valid)
    manifest_path.write_text(source.read_text())
    # Boot entirely from the programmed persistent files: no -bios or -kernel.
    drives = work / 'drives'
    (drives / 'A').mkdir(parents=True)
    console = work / 'camel.txt'
    uart = work / 'uart.txt'
    endpoint = work / 'qmp.sock'
    log = work / 'qemu.log'
    with log.open('w') as output:
        vm = subprocess.Popen([str(qemu), '-M', 'ez80f91-freertos', '-display', 'none',
            '-monitor', 'none', '-nic', 'none', '-serial', 'file:' + str(uart),
            '-qmp', f'unix:{endpoint},server=on,wait=off',
            '-icount', 'shift=5,sleep=off', '-global', f'ez80f91-hostfs.root={drives}',
            '-chardev', f'file,id=camel,path={console}', '-global', 'ez80f91-hostfs.chardev=camel'],
            cwd=state, stdout=output, stderr=output)
        try:
            deadline = time.monotonic() + 45
            while not console.exists() or b'Camel FORTH' not in console.read_bytes():
                assert vm.poll() is None, log.read_text()
                assert time.monotonic() < deadline, (log.read_text(), uart.read_bytes()[-400:])
                time.sleep(.05)
            try:
                flash.program(manifest_path, state, 0)
                raise AssertionError('Live QEMU flash was replaced')
            except RuntimeError:
                pass
            # The CLI shutdown waits until the peer has flushed and exited.
            second_backup = flash.program(manifest_path, state, 0, shutdown=True, qmp=endpoint)
            vm.wait(timeout=10)
            for name, data in snapshots.items():
                assert (state / name).read_bytes() == data
                assert (second_backup / name).read_bytes() == data
            assert sentinel.read_text() == 'KEEP'
            assert b'prvIPTask started' in uart.read_bytes()
            print('PASS: SHA/CRC verification, backups, rollback, live-session guard, clean shutdown and cold boot from persistent flash')
        finally:
            if vm.poll() is None:
                vm.terminate()
                try: vm.wait(timeout=5)
                except subprocess.TimeoutExpired: vm.kill(); vm.wait()
