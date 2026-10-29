"""Observe real DHCP leases and test the original demo via host UDP/TCP sockets."""
import ipaddress
import json
import queue
from pathlib import Path
import socket
import struct
import threading
import time


def dhcp_leases(path):
    """Read complete DHCP ACKs from a possibly still-growing QEMU PCAP."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return []
    if len(data) < 24:
        return []
    endian = '<' if data[:4] == b'\xd4\xc3\xb2\xa1' else '>'
    if data[:4] not in (b'\xd4\xc3\xb2\xa1', b'\xa1\xb2\xc3\xd4'):
        return []
    leases = []
    at = 24
    while at + 16 <= len(data):
        length = struct.unpack_from(endian + 'I', data, at + 8)[0]
        at += 16
        if length > len(data) - at:
            break
        frame = data[at:at + length]
        at += length
        if len(frame) < 42 or frame[12:14] != b'\x08\x00':
            continue
        ip = frame[14:]
        ihl = (ip[0] & 15) * 4
        if ihl < 20 or ip[9] != 17 or len(ip) < ihl + 8:
            continue
        source, dest, size, _ = struct.unpack_from('!HHHH', ip, ihl)
        if (source, dest) != (67, 68):
            continue
        boot = ip[ihl + 8:ihl + size]
        if len(boot) < 240 or boot[0] != 2 or boot[236:240] != bytes.fromhex('63825363'):
            continue
        options = {}
        pos = 240
        while pos < len(boot):
            kind = boot[pos]
            pos += 1
            if kind == 255:
                break
            if kind == 0:
                continue
            if pos >= len(boot):
                break
            count = boot[pos]
            pos += 1
            options[kind] = boot[pos:pos + count]
            pos += count
        if options.get(53) != b'\x05':
            continue
        server = options.get(54, ip[12:16])
        if len(server) != 4:
            continue
        lease = {'server': str(ipaddress.IPv4Address(server)),
                 'address': str(ipaddress.IPv4Address(boot[16:20])),
                 'mac': ':'.join(f'{b:02x}' for b in boot[28:34])}
        if lease not in leases:
            leases.append(lease)
    return leases


class DemoNetworkTest:
    def __init__(self, server, tcp=True):
        self.server = str(ipaddress.IPv4Address(server))
        self.test_tcp = tcp
        self.stage = 0
        self.login = 0
        self.ready = None
        self.mark = 0
        self.address = None
        self.done = False
        self.error = None
        self.udp_ok = False
        self.tcp_ok = False
        self.results = queue.Queue()

    def exchange(self, protocol):
        try:
            size = 1000 if protocol == 'udp' else 4000
            pattern = bytes(i % 251 for i in range(size))
            kind = socket.SOCK_DGRAM if protocol == 'udp' else socket.SOCK_STREAM
            port = 4000 if protocol == 'udp' else 4001
            with socket.socket(socket.AF_INET, kind) as sock:
                sock.settimeout(8)
                sock.connect((self.address, port))
                sock.sendall(pattern)
                received = bytearray()
                while len(received) < size:
                    part = sock.recv(size - len(received))
                    if not part:
                        break
                    received.extend(part)
                if received != pattern:
                    raise RuntimeError(f'{protocol.upper()}-Echo ist nicht bytegleich')
            self.results.put((protocol, None))
        except Exception as error:
            self.results.put((protocol, str(error)))

    def advance(self, output, leases, uart):
        for lease in leases:
            if lease['server'] == self.server and lease['mac'] == '00:90:23:00:01:01':
                self.address = lease['address']
        try:
            protocol, error = self.results.get_nowait()
            if error:
                self.error = f'{protocol.upper()}: {error}'
                raise RuntimeError(self.error)
            if protocol == 'udp':
                self.udp_ok = True
                if not self.test_tcp:
                    self.done = True
            else:
                self.tcp_ok = self.done = True
        except queue.Empty:
            pass
        if self.login == 0 and b'Login:' in output:
            uart.sendall(b'anonymous\r')
            self.login = 1
        elif self.login == 1 and b'Password:' in output:
            uart.sendall(b'anonymous\r')
            self.login = 2
        if self.ready is None and b'ZTP ' in output:
            self.ready = time.monotonic()
        if self.stage == 0 and self.address and self.ready and time.monotonic() - self.ready > .5:
            self.mark = len(output)
            uart.sendall(b'bsdudpserver\r')
            self.stage = 1
        elif self.stage in (1, 4) and b"Enter the server's port number to listen:" in output[self.mark:]:
            uart.sendall(b'4000\r' if self.stage == 1 else b'4001\r')
            self.stage += 1
        elif self.stage == 2 and b'Server is bound to the port 4000' in output[self.mark:]:
            threading.Thread(target=self.exchange, args=('udp',), daemon=True).start()
            self.stage = 3
        elif self.stage == 3 and self.udp_ok and b'Sent 1000 bytes' in output:
            self.mark = len(output)
            uart.sendall(b'bsdtcpserver\r')
            self.stage = 4
        elif self.stage == 5 and b'Server is Listening on port 4001' in output[self.mark:]:
            threading.Thread(target=self.exchange, args=('tcp',), daemon=True).start()
            self.stage = 6

    def report(self):
        return {'dhcp_verified': self.address is not None, 'address': self.address,
                'udp_echo_ok': self.udp_ok, 'tcp_echo_ok': self.tcp_ok, 'error': self.error}


def start_after_bridge(process, qmp_path, bridge, previous_ports, start_cpu=True):
    """Wait for the new TAP's STP forwarding state before starting the guest."""
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    deadline = time.monotonic() + 35
    while True:
        if process.poll() is not None:
            raise RuntimeError('QEMU/Bridge-Helper beendet; siehe qemu.log')
        try:
            connection.connect(str(qmp_path))
            break
        except (FileNotFoundError, ConnectionRefusedError):
            if time.monotonic() >= deadline:
                connection.close()
                raise RuntimeError('QMP-Startzeit überschritten')
            time.sleep(.05)
    connection.settimeout(5)
    try:
        with connection.makefile('rwb', buffering=0) as stream:
            if 'QMP' not in json.loads(stream.readline()):
                raise RuntimeError('Ungültige QMP-Begrüßung')
            def command(name):
                stream.write(json.dumps({'execute': name}).encode() + b'\n')
                while True:
                    response = json.loads(stream.readline())
                    if 'event' in response:
                        continue
                    if 'error' in response:
                        raise RuntimeError(str(response['error']))
                    return
            command('qmp_capabilities')
            wait_for_bridge(process, bridge, previous_ports, deadline)
            if start_cpu:
                command('cont')

    finally:
        connection.close()


def wait_for_bridge(process, bridge, previous_ports, deadline=None):
    ports = Path('/sys/class/net') / bridge / 'brif'
    deadline = deadline or time.monotonic() + 35
    print('Warte auf die Bridge-Freigabe des Gastports ...', flush=True)
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('QEMU beendet; siehe qemu.log')
        for port in ports.iterdir():
            if port.name not in previous_ports:
                try:
                    if (port / 'state').read_text().strip() == '3':
                        print(f'Bridge {bridge}: {port.name} ist forwarding.', flush=True)
                        return
                except FileNotFoundError:
                    continue
        time.sleep(.1)
    raise RuntimeError('Gastport erreicht keinen Bridge-Forwarding-Zustand')
