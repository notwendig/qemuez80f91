#!/usr/bin/env python3
"""Isolated full-firmware DHCP, ICMP and TCP-console test over Ethernet.

Usage: test_freertos_network.py QEMU FIRMWARE.bin [EXTERNAL_FLASH.bin]
Add --debug-reset to test a debugger-provided stack and cleared MADL.
Add --cpm to boot CP/M on TCP 4050 and run DIR.
Add --cli to exercise the firmware command console on UDP 4030.
Add --monitor to validate the actual UDP monitor output in an 80x40 screen.
Add --hostname NAME to check a custom DHCP hostname (default ez800).
With EXTERNAL_FLASH.bin, cold-boot internal flash and attach external flash at 0x100000.
No bridge, external DHCP server or host TCP ports are needed.
"""
import re
import socket
import struct
import sys
import tempfile
import threading
import time
from pathlib import Path
from ez80_testlib import VM

debug_reset = '--debug-reset' in sys.argv
if debug_reset:
    sys.argv.remove('--debug-reset')
cpm_test = '--cpm' in sys.argv
if cpm_test:
    sys.argv.remove('--cpm')
cli_test = '--cli' in sys.argv
if cli_test:
    sys.argv.remove('--cli')
monitor_test = '--monitor' in sys.argv
if monitor_test:
    sys.argv.remove('--monitor')
SERVICE_PORT = 4050 if cpm_test else 4040
hostname = None
if '--hostname' in sys.argv:
    index = sys.argv.index('--hostname')
    hostname = sys.argv[index + 1]
    del sys.argv[index:index + 2]
expected_hostname = (hostname if hostname is not None else 'ez800').encode('ascii')

SERVER_IP = socket.inet_aton('192.168.77.1')
GUEST_IP = socket.inet_aton('192.168.77.123')
SERVER_MAC = bytes.fromhex('020000000001')


def checksum(data):
    data += b'\0' * (len(data) % 2)
    total = sum(struct.unpack('!' + str(len(data) // 2) + 'H', data))
    while total >> 16:
        total = (total & 65535) + (total >> 16)
    return (~total) & 65535


class Peer:
    def __init__(self, wire):
        self.wire = wire
        self.wire.settimeout(.2)
        self.stop = False
        self.lock = threading.Lock()
        self.guest_mac = None
        self.dhcp = []
        self.hostnames = []
        self.errors = []
        self.ping = False
        self.tcp_connected = False
        self.received = bytearray()
        self.local_seq = 0x12345678
        self.remote_seq = None
        self.cli_replies = {}
        self.monitor_packets = []

    def exact(self, size):
        data = bytearray()
        while len(data) < size:
            if self.stop:
                raise EOFError
            try:
                part = self.wire.recv(size - len(data))
            except socket.timeout:
                continue
            if not part:
                raise EOFError
            data.extend(part)
        return bytes(data)

    def ethernet(self, target, protocol, packet):
        frame = target + SERVER_MAC + struct.pack('!H', protocol) + packet
        frame += b'\0' * max(0, 60 - len(frame))
        with self.lock:
            self.wire.sendall(struct.pack('!I', len(frame)) + frame)

    def ipv4(self, protocol, packet, broadcast=False):
        destination = b'\xff' * 4 if broadcast else GUEST_IP
        header = bytearray(struct.pack('!BBHHHBBH4s4s',
                                      0x45, 0, 20 + len(packet), 1, 0,
                                      64, protocol, 0, SERVER_IP, destination))
        header[10:12] = struct.pack('!H', checksum(header))
        self.ethernet(b'\xff' * 6 if broadcast else self.guest_mac,
                      0x0800, header + packet)

    def transport_checksum(self, protocol, packet, broadcast=False):
        destination = b'\xff' * 4 if broadcast else GUEST_IP
        pseudo = SERVER_IP + destination + struct.pack('!BBH', 0, protocol, len(packet))
        return checksum(pseudo + packet) or 65535

    def tcp(self, flags, ack=0, payload=b''):
        packet = bytearray(struct.pack('!HHIIBBHHH', 40000, SERVICE_PORT,
                                      self.local_seq, ack, 0x50, flags, 8192, 0, 0) + payload)
        packet[16:18] = struct.pack('!H', self.transport_checksum(6, packet))
        self.ipv4(6, packet)

    def cli_send(self, payload, source=40100):
        self.udp(payload, 4030, source)

    def udp(self, payload, destination, source):
        packet = bytearray(struct.pack('!HHHH', source, destination, len(payload) + 8, 0) + payload)
        packet[6:8] = struct.pack('!H', self.transport_checksum(17, packet))
        self.ipv4(17, packet)

    def cli_exchange(self, payload, marker, source=40100):
        self.cli_replies[source] = []
        for part in payload if isinstance(payload, tuple) else (payload,):
            self.cli_send(part, source)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            assert not self.errors, self.errors
            packets = self.cli_replies[source]
            if packets and packets[-1] == b'\r\n':
                output = b''.join(packets)
                assert marker in output, (payload, marker, output)
                return output
            time.sleep(.05)
        raise AssertionError(('CLI response timeout', payload, self.cli_replies[source]))

    def send_arp_request(self):
        packet = struct.pack('!HHBBH6s4s6s4s', 1, 0x800, 6, 4, 1,
                             SERVER_MAC, SERVER_IP, b'\0' * 6, GUEST_IP)
        self.ethernet(b'\xff' * 6, 0x806, packet)

    def send_ping(self):
        packet = bytearray(struct.pack('!BBHHH', 8, 0, 0, 0x1234, 1) + b'ez80-upgrade')
        packet[2:4] = struct.pack('!H', checksum(packet))
        self.ipv4(1, packet)

    def dhcp_reply(self, boot):
        options = boot[240:]
        message = None
        name = None
        while options:
            code = options[0]
            options = options[1:]
            if code == 255:
                break
            if code == 0:
                continue
            size = options[0]
            if code == 53:
                message = options[1]
            if code == 12:
                name = options[1:size + 1]
            options = options[size + 1:]
        if message not in (1, 3):
            return
        self.hostnames.append((message, name))
        self.guest_mac = boot[28:34]
        kind = 2 if message == 1 else 5
        self.dhcp.append(kind)
        reply = bytearray(boot[:240])
        reply[0] = 2
        reply[16:20] = GUEST_IP
        reply[20:24] = SERVER_IP
        reply += bytes([53, 1, kind, 54, 4]) + SERVER_IP
        reply += bytes([51, 4]) + struct.pack('!I', 3600)
        reply += bytes([1, 4, 255, 255, 255, 0, 3, 4]) + SERVER_IP
        reply += bytes([6, 4]) + SERVER_IP + bytes([255])
        packet = bytearray(struct.pack('!HHHH', 67, 68, len(reply) + 8, 0) + reply)
        packet[6:8] = struct.pack('!H', self.transport_checksum(17, packet, True))
        self.ipv4(17, packet, True)

    def process(self, frame):
        protocol = frame[12:14]
        if protocol == b'\x08\x06':
            arp = frame[14:42]
            if arp[6:8] == b'\0\1' and arp[24:28] == SERVER_IP:
                reply = struct.pack('!HHBBH6s4s6s4s', 1, 0x800, 6, 4, 2,
                                    SERVER_MAC, SERVER_IP, arp[8:14], arp[14:18])
                self.ethernet(arp[8:14], 0x806, reply)
            return
        if protocol != b'\x08\x00':
            return
        ip = frame[14:]
        header_length = (ip[0] & 15) * 4
        packet = ip[header_length:struct.unpack('!H', ip[2:4])[0]]
        if ip[9] == 17 and packet[:4] == struct.pack('!HH', 68, 67):
            self.dhcp_reply(packet[8:])
        elif ip[9] == 17 and packet[:2] == struct.pack('!H', 4030):
            destination, length = struct.unpack('!HH', packet[2:6])
            self.cli_replies.setdefault(destination, []).append(packet[8:length])
        elif ip[9] == 17 and packet[:2] == struct.pack('!H', 4060):
            length = struct.unpack('!H', packet[4:6])[0]
            self.monitor_packets.append(packet[8:length])
        elif ip[9] == 1 and packet[:2] == b'\0\0' and packet[4:8] == b'\x12\x34\0\1':
            assert packet[8:] == b'ez80-upgrade'
            self.ping = True
        elif ip[9] == 6 and packet[:4] == struct.pack('!HH', SERVICE_PORT, 40000):
            sequence = struct.unpack('!I', packet[4:8])[0]
            flags = packet[13]
            assert not flags & 4, 'TCP listener reset the connection'
            if flags & 2:
                assert struct.unpack('!I', packet[8:12])[0] == 0x12345679
                self.local_seq = 0x12345679
                self.remote_seq = (sequence + 1) & 0xffffffff
                self.tcp(0x10, self.remote_seq)
                self.tcp_connected = True
            payload = packet[(packet[12] >> 4) * 4:]
            if payload and self.remote_seq is not None:
                if sequence == self.remote_seq:
                    self.received.extend(payload)
                    self.remote_seq = (sequence + len(payload)) & 0xffffffff
                self.tcp(0x10, self.remote_seq)

    def run(self):
        try:
            while not self.stop:
                size = struct.unpack('!I', self.exact(4))[0]
                assert 14 <= size <= 65536, size
                self.process(self.exact(size))
        except (EOFError, OSError):
            if not self.stop:
                self.errors.append('Ethernet socket closed unexpectedly')
        except Exception as error:
            self.errors.append(repr(error))


with tempfile.TemporaryDirectory(prefix='f91-network-') as directory:
    uart = Path(directory) / 'uart.txt'
    flash_boot = len(sys.argv) == 4
    if flash_boot:
        (Path(directory) / 'ez80f91_100000.0').write_bytes(Path(sys.argv[3]).read_bytes())
    host, guest = socket.socketpair()
    peer = Peer(host)
    vm = VM(Path(sys.argv[2]).resolve(), 'file:' + str(uart),
            extra=('-icount', 'shift=5,sleep=off', '-nic', f'socket,fd={guest.fileno()}',
                   '-global', 'ez80f91-emac.phy-addr=31',
                   *(['-global', f'ez80f91-memory.hostname={hostname}'] if hostname is not None else []),
                   *(['-gdb', f'unix:{directory}/gdb.sock,server=on,wait=off'] if debug_reset else [])),
            pass_fds=(guest.fileno(),),
            machine='ez80f91-freertos' if flash_boot else 'ez80f91-freertos,ram-boot=on',
            loader='-bios' if flash_boot else '-kernel', cwd=directory)
    if debug_reset:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/zds'))
        from rsp import RSP
        debugger = RSP(unix=f'{directory}/gdb.sock')
        registers = debugger.registers()
        registers[9] = 0xC80000
        registers[18] = 1
        registers[19] = 0
        debugger.set_registers(registers)
    guest.close()
    thread = threading.Thread(target=peer.run)
    thread.start()
    try:
        vm.cmd('cont')
        deadline = time.monotonic() + (300 if cpm_test else 90)
        started = False
        command_sent = False
        retry_at = 0.0
        while time.monotonic() < deadline:
            assert not peer.errors, peer.errors
            data = uart.read_bytes()
            if not started and b'IP Address:            192.168.77.123\n' in data and b'LISTEN' in data:
                assert 2 in peer.dhcp and 5 in peer.dhcp, peer.dhcp
                peer.send_arp_request()
                started = True
            if started and time.monotonic() >= retry_at:
                if not peer.ping:
                    peer.send_ping()
                if not peer.tcp_connected:
                    peer.tcp(2)
                retry_at = time.monotonic() + 1
            if cpm_test and b'a>' in peer.received.lower():
                if not command_sent:
                    peer.received.clear()
                    peer.tcp(0x18, peer.remote_seq, b'DIR\r')
                    peer.local_seq += 4
                    command_sent = True
                elif b'COM' in peer.received.upper():
                    break
            elif not cpm_test and peer.ping and peer.tcp_connected and b'UT ' in peer.received:
                break
            time.sleep(.1)
        if cli_test:
            output = peer.cli_exchange(b'help\n', b'ip-config')
            for command in (b'dump', b'ihex', b'date', b'time', b'ping'):
                assert command in output, output
            peer.cli_exchange((b'ip-', b'config\r\n'), b'192.168.77.123')
            peer.cli_exchange(b'time 12 34 56\n', b'12:34:56')
            peer.cli_exchange(b'date 5 6 11 2026\n', b'2026')
            peer.cli_exchange(b'dump b 0 16\n', b'000000:')
            peer.cli_exchange(b'dump b 0 -16\n', b'000000:')
            peer.cli_exchange(b'dump b 0xfffff0 32\n', b'wrong addres range')
            peer.cli_exchange(b'ihex 0 16\n', b':00000001FF')
            peer.cli_exchange(b'echo-3-parameters first second third\n', b'3: third')
            peer.cli_exchange(b'unknown-command\n', b'Command not recognised')
            peer.cli_exchange(b'echo-3-parameters one\n', b'Incorrect command parameter')
            peer.cli_exchange(b'x' * 80 + b'\n', b'Command too long')
            peer.cli_exchange(b'ip-config\n', b'192.168.77.123')
            peer.cli_send(b'hel')
            peer.cli_exchange(b'help\n', b'ip-config', source=40101)
            peer.cli_exchange(b'ip-config\n', b'192.168.77.123')
            print('PASS: UDP CLI help, fragmented input, RTC, dump, Intel HEX, errors, overflow recovery and new clients', flush=True)
        if monitor_test:
            peer.udp(b'\n', 4060, 40120)
            deadline = time.monotonic() + 20
            retry_at = time.monotonic() + 1
            while time.monotonic() < deadline:
                output = b''.join(peer.monitor_packets)
                if not output and time.monotonic() >= retry_at:
                    peer.udp(b'\n', 4060, 40120)
                    retry_at = time.monotonic() + 1
                if all(marker in output for marker in (b'Ethernet', b'Real Time Clock', b'Heap', b'Platform buttons', b'Last tick', b'Right')):
                    break
                time.sleep(.05)
            else:
                raise AssertionError(('Monitor output timeout', output[-2000:], uart.read_bytes()[-2000:]))
            # Check emitted cursor positions and field widths, including DEC save/restore.
            tokens = re.finditer(rb'\x1b\[([0-9;?]*)([A-Za-z])|\x1b([78])|([^\x1b])', output)
            row, column, saved = 1, 1, (1, 1)
            for token in tokens:
                if token[2] in (b'H', b'f'):
                    values = token[1].split(b';')
                    row, column = (int(value or b'1') for value in values)
                    assert 1 <= row <= 40 and 1 <= column <= 80, token[0]
                elif token[3] == b'7':
                    saved = row, column
                elif token[3] == b'8':
                    row, column = saved
                elif token[4]:
                    character = token[4][0]
                    assert character >= 32 or character in (9, 10, 13), (
                        'Unexpected monitor control byte', row, column, token[4])
                    if character >= 32:
                        assert column <= 80, ('Monitor field overflows', row, column, token[4])
                        column += 1
            capture = Path(__file__).resolve().parents[1] / 'build/freertos-cli/monitor.ansi'
            capture.parent.mkdir(parents=True, exist_ok=True)
            capture.write_bytes(output)
            print('PASS: live UDP monitor fields stay inside 80x40; captured ANSI output', flush=True)
        vm.cmd('stop')
        assert peer.ping, ('ICMP echo timeout', uart.read_bytes()[-1500:])
        service_ok = (command_sent and b'COM' in peer.received.upper() and b'a>' in peer.received.lower()) if cpm_test else b'UT ' in peer.received
        assert peer.tcp_connected and service_ok, (
            'TCP console timeout', bytes(peer.received), uart.read_bytes()[-1500:])
        if flash_boot:
            # Check that board startup attached the external image at its fixed address.
            prefix = Path(sys.argv[3]).read_bytes()[:16]
            memory = vm.hmp('xp /16bx 0x100000')
            values = bytes(int(value, 16) for value in re.findall(r'0x([0-9a-fA-F]{2})\b', memory))
            assert values == prefix, (memory, prefix)
        diagnostics = uart.read_bytes() + bytes(peer.received)
        assert b'EMAC 100MBPS, FULL_DUPLEX, Link up' in diagnostics, diagnostics
        assert (1, expected_hostname) in peer.hostnames, peer.hostnames
        assert (3, expected_hostname) in peer.hostnames, peer.hostnames
        assert b'vDHCPProcess: offer 192.168.77.123' in diagnostics, diagnostics
        assert b'ipARP_REQUEST from 192.168.77.1 to 192.168.77.123 end-point 192.168.77.123' in diagnostics, diagnostics
        assert b'255.168.77.' not in diagnostics, diagnostics
    finally:
        peer.stop = True
        vm.close()
        host.close()
        thread.join(2)
print('PASS: DHCP hostname ' + expected_hostname.decode() + ', ARP, ICMP, ' + ('CP/M boot and DIR' if cpm_test else 'TCP console') + ' and full-width IPv4 diagnostics')
