"""Open a dedicated UART terminal and serialize eZ80 instances by debug port."""
import fcntl
import argparse
import json
import os
import re
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
from demo_network import host_link_options, start_after_bridge


def lock_port(port):
    # Persistent lock files must not be unlinked while another starter can wait.
    directory = Path('/tmp') / f'ez80f91-{os.getuid()}'
    directory.mkdir(mode=0o700, exist_ok=True)
    lock = (directory / f'{port}.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise RuntimeError(f'eZ80f91.{port} läuft bereits.') from None
    return lock


def check_port(port):
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(('0.0.0.0', port))
        except OSError as error:
            raise RuntimeError(f'Debugport {port} ist bereits belegt: {error}') from None


def check_qemu(qemu):
    result = subprocess.run([qemu, '-M', 'ez80f91-minimal,help'],
                            capture_output=True, text=True, timeout=10)
    if result.returncode or not all(option in result.stdout + result.stderr
                                    for option in ('wd2797a=', 'hostname=')):
        raise RuntimeError(f'QEMU unter {qemu} unterstützt WD2797A/Hostname nicht. '
                           'Die installierte QEMU-Version muss aktualisiert werden.')


def disk_directory(port, supplied=None):
    if supplied is not None:
        directory = supplied.resolve()
        if not directory.is_dir():
            raise RuntimeError(f'Disk-Verzeichnis fehlt: {directory}')
        return directory
    directory = Path.cwd() / f'ez80f91_disks.{port}'
    directory.mkdir(exist_ok=True)
    source = Path(__file__).resolve().parents[1] / 'images/cpm'
    legacy = Path.cwd() / f'ez80f91_cs3.{port}'
    layout = json.loads((source / 'layout.json').read_text())
    raw = legacy.read_bytes() if legacy.exists() else None
    if raw is not None and len(raw) != sum(disk['size'] for disk in layout):
        raise RuntimeError(f'Unerwartete Größe des bisherigen CS3-Images: {legacy}')
    for disk in layout:
        name = disk['drive'] + '.img'
        target = directory / name
        if target.exists():
            continue
        if raw is None:
            shutil.copyfile(source / name, target)
        else:
            target.write_bytes(raw[disk['offset']:disk['offset'] + disk['size']])
    return directory


def terminal_session(port, qemu, run=False, kit=False, dev=None, devport=0x1000, hostname=None):
    with lock_port(port) as lock:
        check_port(port)
        child = None
        kit_child = None
        stopped = False

        def stop(signum, frame):
            nonlocal stopped
            stopped = True
            if child is not None and child.poll() is None:
                child.terminate()

        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, stop)
        status = 'CPU startet aus Flash.' if run else 'CPU wartet auf den Debugger.'
        print(f'eZ80f91.{port} — UART0; {status}\n'
              'Strg-C oder Fenster schließen beendet QEMU und speichert Flash.', flush=True)
        qmp_path = Path(lock.name).with_suffix('.qmp')
        uart_log = Path(lock.name).with_suffix('.uart.log')
        kit_state = Path(lock.name).with_suffix('.kit.json')
        kit_options = []
        hostname = hostname if hostname is not None else f'ez80{port}'
        print(f'Hostname: {hostname}', flush=True)
        directory = disk_directory(port, dev)
        disk_options = ['-global', f'ez80f91-memory.dev-dir={directory}',
                        '-global', f'ez80f91-memory.wd2797a={devport}']
        print(f'CP/M: {directory}; WD2797A-Basisport {devport:#x}', flush=True)
        if kit:
            kit_state.unlink(missing_ok=True)
            kit_options = ['-global', f'ez80f91-memory.kit-led-state={kit_state}']
        ports = Path('/sys/class/net/br0/brif')
        if not ports.is_dir():
            raise RuntimeError('Netzwerkbridge br0 fehlt; Demo benötigt das nadibox-Netz.')
        previous_ports = {p.name for p in ports.iterdir()}
        network = ['-nic', 'bridge,id=wire,br=br0,helper=/usr/libexec/qemu-bridge-helper',
                   '-qmp', f'unix:{qmp_path},server=on,wait=off']
        qmp_path.unlink(missing_ok=True)
        print('Netz: br0; AMD-PHY 31; DHCP von nadibox. UART-Protokoll: ' + str(uart_log), flush=True)
        try:
            child = subprocess.Popen([
                qemu, '-M', 'ez80f91-minimal,cs3=none', f'--dbgport={port}', '--scan-dev',
                '-S', '-display', 'none', '-monitor', 'none',
                '-chardev', f'stdio,id=uart,logfile={uart_log}', '-serial', 'chardev:uart',
                '-rtc', 'base=utc,clock=host',
                '-icount', 'shift=5,sleep=off', '-global', 'ez80f91-emac.phy-addr=31',
                '-global', f'ez80f91-memory.hostname={hostname}',
                *host_link_options('br0'), *network, *kit_options, *disk_options],
                pass_fds=(lock.fileno(),))
            if kit:
                kit_child = subprocess.Popen([sys.executable,
                    str(Path(__file__).with_name('kit.py')), str(kit_state), '--port', str(port), '--qmp', str(qmp_path)])
            if stopped:
                child.terminate()
            else:
                start_after_bridge(child, qmp_path, 'br0', previous_ports, start_cpu=run)
            return child.wait()
        finally:
            if child is not None and child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
            qmp_path.unlink(missing_ok=True)
            if kit_child is not None and kit_child.poll() is None:
                kit_child.terminate()
                kit_child.wait(timeout=5)
            kit_state.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--session', action='store_true')
    mode.add_argument('--launch', action='store_true')
    parser.add_argument('port', type=int)
    parser.add_argument('qemu', type=Path)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--kit', action='store_true')
    parser.add_argument('--dev', type=Path)
    parser.add_argument('--hostname', help='DHCP-Hostname (Standard: ez80<Debugport>)')
    parser.add_argument('--wd2797a', '--devport', dest='devport', type=lambda value: int(value, 0), default=0x1000)
    args = parser.parse_args()
    if not 0x100 <= args.devport <= 0xfff8 or 0xfef9 <= args.devport <= 0xff4b:
        parser.error('--wd2797a benötigt 8 externe Ports; Basis 0x100..0xfff8, Bereich 0xff00..0xff4b ist reserviert')
    if args.hostname is None:
        args.hostname = f'ez80{args.port}'
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', args.hostname):
        parser.error('--hostname: 1..63 ASCII-Buchstaben/Ziffern, Bindestriche nur im Inneren')
    if args.dev is not None:
        if not args.dev.is_dir():
            parser.error(f'Disk-Verzeichnis fehlt: {args.dev}')
        if not any((args.dev / name).is_file() for drive in 'ABCDEFGHIJKLMNOP'
                   for name in (drive, drive + '.img')):
            parser.error(f'Keine Dateien A.img..P.img oder A..P in {args.dev}')
    port, qemu, run, kit = args.port, str(args.qemu.resolve()), args.run, args.kit
    check_qemu(qemu)
    if args.session:
        return terminal_session(port, qemu, run, kit, args.dev, args.devport, args.hostname)
    # Fail before opening a window; the terminal child rechecks under its lock.
    with lock_port(port):
        check_port(port)
    command = [sys.executable, str(Path(__file__).resolve()), '--session', str(port), qemu]
    command.extend(['--wd2797a', str(args.devport)])
    command.extend(['--hostname', args.hostname])
    if args.dev:
        command.extend(['--dev', str(args.dev.resolve())])
    if run:
        command.append('--run')
    if kit:
        command.append('--kit')
    title = f'eZ80f91.{port}'
    if shutil.which('gnome-terminal'):
        terminal = ['gnome-terminal', '--wait', f'--title={title}',
                    f'--working-directory={Path.cwd()}', '--', *command]
    elif shutil.which('xterm'):
        terminal = ['xterm', '-T', title, '-e', *command]
    else:
        raise RuntimeError('Kein UART-Terminal gefunden (gnome-terminal oder xterm benötigt).')
    terminal_env = os.environ.copy()
    # A closed parent terminal may leave stale D-Bus screen/service IDs.
    for name in ('GNOME_TERMINAL_SCREEN', 'GNOME_TERMINAL_SERVICE'):
        terminal_env.pop(name, None)
    return subprocess.call(terminal, env=terminal_env)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f'start.sh: {error}', file=sys.stderr)
        sys.exit(1)
