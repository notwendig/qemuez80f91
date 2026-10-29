"""Open a dedicated UART terminal and serialize eZ80 instances by debug port."""
import fcntl
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
from demo_network import start_after_bridge


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


def terminal_session(port, qemu, run=False, kit=False):
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
                qemu, '-M', 'ez80f91-minimal', f'--dbgport={port}', '--scan-dev',
                '-S', '-display', 'none', '-monitor', 'none',
                '-chardev', f'stdio,id=uart,logfile={uart_log}', '-serial', 'chardev:uart',
                '-rtc', 'base=utc,clock=host',
                '-icount', 'shift=5,sleep=off', '-global', 'ez80f91-emac.phy-addr=31',
                *network, *kit_options], pass_fds=(lock.fileno(),))
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
    session = sys.argv[1] == '--session'
    port = int(sys.argv[2])
    qemu = str(Path(sys.argv[3]).resolve())
    run = '--run' in sys.argv[4:]
    kit = '--kit' in sys.argv[4:]
    if session:
        return terminal_session(port, qemu, run, kit)
    # Fail before opening a window; the terminal child rechecks under its lock.
    with lock_port(port):
        check_port(port)
    command = [sys.executable, str(Path(__file__).resolve()), '--session', str(port), qemu]
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
    return subprocess.call(terminal)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f'start.sh: {error}', file=sys.stderr)
        sys.exit(1)
