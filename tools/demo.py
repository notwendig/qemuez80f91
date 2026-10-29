"""Build and run the original ZTP TCPUDPDemo on the nadibox network bridge."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import termios
import time
import tty

ROOT = Path(__file__).resolve().parents[1]
from tools.demo_network import DemoNetworkTest, dhcp_leases, start_after_bridge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu', type=Path, default=Path(os.environ.get(
        'QEMU_EZ80', '/tmp/qemuez80f91-build-baseline/qemu-system-ez80')))
    parser.add_argument('--zds', type=Path, default=Path(os.environ.get(
        'ZDS_HOME', str(Path.home() / '.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5'))))
    parser.add_argument('--out', type=Path, default=ROOT / 'build/ztp-tcpudp-ram')
    parser.add_argument('--rebuild', action='store_true', help='Demo neu übersetzen')
    parser.add_argument('--prepare-only', action='store_true', help='Nur Build vorbereiten')
    parser.add_argument('--test', action='store_true', help='DHCP von nadibox sowie UDP/TCP über das reale Netz prüfen')
    parser.add_argument('--seconds', type=float, help='Nach dieser Laufzeit beenden (Test: Standard 30 s)')
    parser.add_argument('--bridge', default='br0', help='Bridge zum nadibox-Netz (Standard: br0)')
    parser.add_argument('--dhcp-server', default='192.168.77.1', help='Erwartete nadibox-DHCP-Adresse')
    parser.add_argument('--bridge-helper', type=Path, default=Path('/usr/libexec/qemu-bridge-helper'))
    parser.add_argument('--dbgport', type=int, help='ZDS-II-Debugport mit Scan Device; CPU wartet auf den Debugger')
    for cs in range(4):
        parser.add_argument(f'--cs{cs}', choices=('ram', 'flash', 'none'),
                            help=f'Speichertyp an CS{cs} (Board-Einstellung)')
    args = parser.parse_args()
    if args.dbgport is not None and (not 1 <= args.dbgport <= 65535 or args.test):
        parser.error('--dbgport benötigt Port 1..65535 und interaktiven Betrieb ohne --test')
    if args.seconds is not None and args.seconds <= 0:
        parser.error('--seconds muss größer als null sein')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'start.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('Dieses Demo läuft bereits; vorhandenen Starter zuerst beenden.')
        if not args.qemu.is_file():
            parser.error(f'QEMU nicht gefunden: {args.qemu}')
        valid = False
        try:
            metadata = json.loads((out / 'build.json').read_text())
            valid = (metadata['filesystem'] == 'ram' and metadata['memory_profile'] == 'qemu'
                     and Path(metadata['project']).resolve() == (args.zds.resolve() /
                         'ZTP2.5.1/ZTP/SamplePrograms/TCPUDPDemo')
                     and hashlib.sha256((out / 'tcpudp.bin').read_bytes()).hexdigest()
                     == metadata['sha256'])
        except (OSError, ValueError, KeyError):
            pass
        if args.rebuild or not valid:
            subprocess.run([sys.executable, str(ROOT / 'examples/ztp_tcpudp/build.py'),
                            '--zds', str(args.zds.resolve()), '--filesystem', 'ram',
                            '--out', str(out)], check=True)
        if args.prepare_only:
            print(out / 'tcpudp.bin')
            return 0
        if not args.bridge_helper.is_file():
            parser.error(f'QEMU-Bridge-Helper nicht gefunden: {args.bridge_helper}')
        return console(args.qemu.resolve(), out, args.seconds or (30 if args.test else None),
                       args.bridge, args.bridge_helper, args.dhcp_server, args.test,
                       tuple(getattr(args, f'cs{cs}') for cs in range(4)), args.dbgport)


def console(qemu, out, seconds, bridge, helper, server, test, cs_kind=(), dbgport=None):
    uart, uart_guest = socket.socketpair()
    process = None
    saved_terminal = None
    stdin_open = True
    output = bytearray()
    result = DemoNetworkTest(server) if test else None
    machine = 'ez80f91-freertos,ram-boot=on,osc-frequency=5000000'
    machine += ''.join(f',cs{cs}={kind}' for cs, kind in enumerate(cs_kind) if kind)
    previous_term = signal.getsignal(signal.SIGTERM)

    def terminate(signum, frame):
        raise KeyboardInterrupt

    qmp_path = out / 'demo-qmp.sock'
    qmp_path.unlink(missing_ok=True)
    ports = Path('/sys/class/net') / bridge / 'brif'
    if not ports.is_dir():
        raise RuntimeError(f'Netzwerkbridge nicht gefunden: {bridge}')
    previous_ports = {port.name for port in ports.iterdir()}
    try:
        signal.signal(signal.SIGTERM, terminate)
        with (out / 'qemu.log').open('wb') as qemu_log, (out / 'uart.log').open('wb') as uart_log:
            process = subprocess.Popen([
                str(qemu), '-M', machine,
                '-S', '-qmp', f'unix:{qmp_path},server=on,wait=off',
                '-kernel', str(out / 'tcpudp.bin'), '-display', 'none', '-monitor', 'none',
                '-chardev', f'socket,id=console,fd={uart_guest.fileno()}',
                '-serial', 'chardev:console', '-icount', 'shift=5,sleep=off',
                '-nic', f'bridge,id=wire,br={bridge},helper={helper}',
                '-object', f'filter-dump,id=demo-capture,netdev=wire,file={out / "network.pcap"}',
                *([f'--dbgport={dbgport}', '--scan-dev'] if dbgport else []),
                '-global', 'ez80f91-emac.phy-addr=31',
                '-d', 'unimp,guest_errors', '-D', str(out / 'devices.log')],
                pass_fds=(uart_guest.fileno(),),
                stdin=subprocess.DEVNULL, stdout=qemu_log, stderr=subprocess.STDOUT)
            uart_guest.close()
            start_after_bridge(process, qmp_path, bridge, previous_ports, start_cpu=not dbgport)
            print('TCPUDPDemo – App-Konsole | Login: anonymous / anonymous', flush=True)
            print(f'Netz: {bridge} | DHCP: nadibox ({server}) | RAM-Dateisystem.', flush=True)
            if dbgport:
                print(f'ZDS II: Debugport {dbgport}, Scan Device UDP 3000; CPU wartet auf Run.', flush=True)
            print('Befehle: help, bsdudpserver, bsdtcpserver | Beenden: Strg+C oder Strg+]', flush=True)
            if sys.stdin.isatty() and not test:
                saved_terminal = termios.tcgetattr(sys.stdin.fileno())
                tty.setraw(sys.stdin.fileno())
            deadline = time.monotonic() + seconds if seconds else float('inf')
            while process.poll() is None and time.monotonic() < deadline:
                readers = [uart] + ([sys.stdin.buffer] if stdin_open and not test else [])
                ready, _, _ = select.select(readers, [], [], .1)
                if uart in ready:
                    data = uart.recv(65536)
                    if not data:
                        break
                    output.extend(data)
                    uart_log.write(data)
                    uart_log.flush()
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                leases = dhcp_leases(out / 'network.pcap')
                for lease in leases:
                    if lease['mac'] == '00:90:23:00:01:01' and lease['server'] != server:
                        raise RuntimeError(f'Falscher DHCP-Server: {lease["server"]}; erwartet nadibox ({server})')
                if result is not None:
                    result.advance(bytes(output), leases, uart)
                    if result.done:
                        break
                if stdin_open and sys.stdin.buffer in ready:
                    data = os.read(sys.stdin.fileno(), 4096)
                    if not data:
                        stdin_open = False
                        if seconds is None:
                            break
                    elif b'\x03' in data or b'\x1d' in data:
                        break
                    else:
                        uart.sendall(data)
            code = process.poll()
            if code not in (None, 0):
                raise RuntimeError(f'QEMU beendet mit Status {code}; siehe {out}/qemu.log')
    except KeyboardInterrupt:
        pass
    finally:
        if saved_terminal is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, saved_terminal)
        signal.signal(signal.SIGTERM, previous_term)
        if process is not None:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for sock in (uart, uart_guest):
            sock.close()
        report = {'bridge': bridge, 'expected_dhcp_server': server,
                  'leases': dhcp_leases(out / 'network.pcap')}
        if result is not None:
            report.update(result.report())
        (out / 'network.json').write_text(json.dumps(report, indent=2) + '\n')
        qmp_path.unlink(missing_ok=True)
        print('\nTCPUDPDemo beendet.', flush=True)
    if result is not None:
        if not result.done:
            raise RuntimeError(result.error or 'Netzwerktest nicht abgeschlossen; siehe uart.log/network.json')
        print('PASS: nadibox-DHCP, 1000 Byte UDP und 4000 Byte TCP', flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
