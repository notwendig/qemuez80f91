#!/usr/bin/env python3
"""Program persistent QEMU flash from an IDE-free firmware build, with backups."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import struct
import sys
import tempfile
import time
import zlib

from firmware import ROOT, DEFAULT_PROJECT, default_zds, build


def runtime(port):
    return Path('/tmp') / f'ez80f91-{os.getuid()}' / f'{port}'


def stop(port, qmp=None):
    path = qmp or runtime(port).with_suffix('.qmp')
    if not path.exists():
        print(f'No Kit QMP session on port {port}.')
        return
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(5)
        try:
            sock.connect(str(path))
        except (ConnectionRefusedError, FileNotFoundError):
            return
        peer_pid = struct.unpack('3i', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[0]
        stream = sock.makefile('rwb', buffering=0)
        greeting = json.loads(stream.readline())
        if 'QMP' not in greeting:
            raise RuntimeError(f'Not a QEMU monitor: {path}')
        for command in ('qmp_capabilities', 'quit'):
            stream.write((json.dumps({'execute': command, 'id': command}) + '\n').encode())
            while True:
                line = stream.readline()
                if not line:
                    if command == 'quit':
                        break
                    raise RuntimeError('QMP connection closed')
                reply = json.loads(line)
                if 'event' in reply:
                    continue
                if 'error' in reply:
                    raise RuntimeError(str(reply['error']))
                if reply.get('id') == command:
                    break
    deadline = time.monotonic() + 10
    while True:
        try:
            status = (Path('/proc') / str(peer_pid) / 'stat').read_text().rsplit(')', 1)[1].split()[0]
            if status == 'Z':
                break
        except FileNotFoundError:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(f'QEMU {peer_pid} did not finish saving flash after shutdown')
        time.sleep(.05)
    print(f'QEMU {port}: clean shutdown and flash flush completed.')


@contextlib.contextmanager
def offline(directory, port):
    # Use exactly the same lock as the Qt launcher. QEMU inherits this lock,
    # so it remains held through its final persistent-flash flush.
    base = runtime(port).parent
    base.mkdir(mode=0o700, exist_ok=True)
    with (base / f'{port}.lock').open('a+b') as lock:
        deadline = time.monotonic() + 10
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f'QEMU {port} is still running. Use --stop or close the Kit first.')
                time.sleep(.05)
        if port:
            with socket.socket() as probe:
                probe.settimeout(.15)
                if probe.connect_ex(('127.0.0.1', port)) == 0:
                    raise RuntimeError(f'Port {port} is in use; refusing to replace live flash.')
        # Also catch directly started QEMU processes that do not use the Kit lock.
        for item in Path('/proc').iterdir():
            if not item.name.isdigit():
                continue
            try:
                argv = (item / 'cmdline').read_bytes().split(b'\0')
                if not argv or Path(os.fsdecode(argv[0])).name != 'qemu-system-ez80':
                    continue
                if (item / 'cwd').resolve() != directory:
                    continue
                text = [os.fsdecode(x) for x in argv if x]
                selected = f'--dbgport={port}' in text or any(
                    a == '--dbgport' and i + 1 < len(text) and text[i + 1] == str(port)
                    for i, a in enumerate(text))
                if selected or port == 0 and not any('dbgport' in x for x in text):
                    raise RuntimeError(f'QEMU PID {item.name} still uses this flash directory.')
            except (OSError, ValueError):
                continue
        yield


def atomic(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name + '-', delete=False) as f:
        staged = Path(f.name)
        try:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            staged.unlink(missing_ok=True)
            raise
    try:
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)


def program(manifest_path, directory, port, shutdown=False, qmp=None):
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text())
    images = []
    regions = []
    for image in manifest['images']:
        base, size, filename = image['base'], image['size'], image['file']
        if not isinstance(base, int) or not isinstance(size, int) or size <= 0:
            raise ValueError('Invalid flash geometry in manifest')
        if not (base == 0 and size == 0x40000 or base == 0x40000 and size == 0x100000):
            raise ValueError('Flash manifest must use internal 000000..03FFFF and external 040000..13FFFF')
        if any(base < end and start < base + size for start, end in regions):
            raise ValueError('Overlapping flash images')
        regions.append((base, base + size))
        if Path(filename).name != filename:
            raise ValueError('Image filename must be local to the build manifest')
        data = (manifest_path.parent / filename).read_bytes()
        if len(data) != size or hashlib.sha256(data).hexdigest() != image['sha256']:
            raise ValueError(f'Build image changed or truncated: {filename}; rebuild first')
        images.append((f'ez80f91_{base:X}.{port}', data + zlib.crc32(data).to_bytes(4, 'little')))
    if not images:
        raise ValueError('No flash images in manifest')
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    if shutdown:
        stop(port, qmp)
    with offline(directory, port):
        previous = {}
        for name, _ in images:
            path = directory / name
            if path.is_symlink():
                raise ValueError(f'Refusing to replace symlink: {path}')
            previous[name] = path.read_bytes() if path.exists() else None
        stamp = time.strftime('%Y%m%d-%H%M%S', time.gmtime()) + f'-{os.getpid()}'
        backup_root = manifest_path.parent / 'flash-backups'
        backup_root.mkdir(parents=True, exist_ok=True)
        backup = Path(tempfile.mkdtemp(prefix=stamp + '-', dir=backup_root))
        for name, data in previous.items():
            if data is not None:
                (backup / name).write_bytes(data)
        shutil.copyfile(manifest_path, backup / 'build.json')
        changed = []
        try:
            for name, data in images:
                path = directory / name
                atomic(path, data)
                changed.append(name)
                if path.read_bytes() != data:
                    raise RuntimeError(f'Flash verification failed: {path}')
                print(f'Programmed and verified: {path} ({len(data) - 4} bytes + CRC32)')
        except BaseException:
            for name in changed:
                path = directory / name
                if previous[name] is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic(path, previous[name])
            print('Flash replacement failed; previous images restored.', file=sys.stderr)
            raise
        print(f'Previous flash backed up in: {backup}')
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=DEFAULT_PROJECT)
    parser.add_argument('--config', choices=['Debug', 'Release'], default='Release')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--zds', type=Path, default=default_zds())
    parser.add_argument('--wine-prefix', type=Path, default=Path(os.environ.get('WINEPREFIX', '/tmp/qemuez80f91-zds-wine')))
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--directory', type=Path, default=ROOT, help='QEMU working directory containing its persistent flash')
    parser.add_argument('--port', type=int, default=4040, help='QEMU debug port; 0 for an instance without --dbgport')
    parser.add_argument('--qmp', type=Path, help='Override the Kit QMP socket (e.g. isolated tests)')
    parser.add_argument('--build', action='store_true', help='Build first; leave running emulator untouched if compilation fails')
    parser.add_argument('--rebuild', action='store_true')
    parser.add_argument('--stop', action='store_true', help='Cleanly stop the selected Kit/QEMU session before programming')
    parser.add_argument('--stop-only', action='store_true')
    parser.add_argument('--run', action='store_true', help='Boot the programmed firmware in the Kit after verification')
    parser.add_argument('--bridge', default='br0', help='Network bridge for --run; none for offline mode')
    args = parser.parse_args()
    try:
        if not 0 <= args.port <= 65535:
            raise ValueError('Port must be in 0..65535')
        if args.stop_only:
            stop(args.port, args.qmp)
            return 0
        manifest = build(args) if args.build else args.manifest or (args.out or ROOT / 'build/firmware' / args.config) / 'build.json'
        program(manifest, args.directory, args.port, args.stop, args.qmp)
        if args.run:
            if not args.port:
                raise ValueError('--run requires a nonzero Kit debug port')
            os.chdir(args.directory)
            command = [str(ROOT / 'tools/platform.sh'), 'start', '--machine', 'ez80f91-freertos',
                       '--port', str(args.port), '--run', '--kit', '--wd2797a', '0x18',
                       '--fs-root', str(ROOT / 'cpm-files'), '--bridge', args.bridge]
            os.execv(command[0], command)
    except (ValueError, RuntimeError, OSError) as error:
        print(f'flash_firmware: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
