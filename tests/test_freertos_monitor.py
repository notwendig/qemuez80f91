#!/usr/bin/env python3
"""Live UDP SysInfo reconnect test with a new source port for each nc-like client."""
import socket
import sys
import time

host = sys.argv[1] if len(sys.argv) > 1 else 'ez804040'
port = int(sys.argv[2]) if len(sys.argv) > 2 else 4060
address = socket.gethostbyname(host)
print(f'Monitor: {host} ({address}):{port}', flush=True)

def receive_until(client, marker, timeout=20, retry=False):
    output = bytearray()
    deadline = time.monotonic() + timeout
    retry_at = time.monotonic() + 1
    while time.monotonic() < deadline:
        try:
            data = client.recv(8192)
        except socket.timeout:
            if retry and time.monotonic() >= retry_at:
                client.send(b'\n')
                retry_at = time.monotonic() + 1
            continue
        output += data
        if marker in output:
            return output
    raise AssertionError(f'UDP monitor timeout waiting for {marker!r}: {bytes(output[-300:])!r}')

clients = []
try:
    for attempt in range(3):
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        clients.append(client)
        client.bind(('0.0.0.0', 0))
        client.connect((address, port))
        client.settimeout(.5)
        client.send(b'\n')
        receive_until(client, b'FreeRTOS', timeout=60, retry=True)
        receive_until(client, b'Ethernet')
        print(f'PASS: client {attempt + 1}, source port {client.getsockname()[1]} receives banner and updates', flush=True)
        # Keep old ports alive to verify updates actually move to the new peer.
        for old in clients[:-1]:
            old.setblocking(False)
            try:
                while old.recv(8192):
                    pass
            except BlockingIOError:
                pass
        receive_until(client, b'Heap', timeout=30)
        for old in clients[:-1]:
            try:
                stale = old.recv(8192)
            except BlockingIOError:
                continue
            raise AssertionError(f'Monitor still sends to old source port: {stale[:100]!r}')
finally:
    for client in clients:
        client.close()
print('PASS: UDP monitor reconnects across three source ports; old peers stop receiving')
