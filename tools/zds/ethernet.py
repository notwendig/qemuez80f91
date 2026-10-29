#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Expose a local QEMU eZ80F91 as an Ethernet Smart Cable for ZDS II."""

import argparse
import logging
import socket
import re
import select
import threading
from dtl import DTL
from zdi import ZDI
from rsp import RSP


def receive(sock, size):
    result = bytearray()
    while len(result) < size:
        chunk = sock.recv(size - len(result))
        if not chunk:
            raise EOFError
        result.extend(chunk)
    return bytes(result)


def decode_script(raw):
    # DLL inserts binary payloads after []=<hex byte count>:, including NULs.
    result = bytearray()
    position = 0
    marker = re.compile(rb"\[\]=([0-9A-Fa-f]+):")
    while match := marker.search(raw, position):
        count = int(match[1], 16)
        start = match.end()
        end = start + count
        if end > len(raw):
            raise ValueError("truncated binary DTL buffer")
        result.extend(raw[position : match.start()])
        result.extend(b'[]="')
        result.extend(raw[start:end].hex().encode())
        result.extend(b'"')
        position = end
    result.extend(raw[position:])
    return result.decode("ascii")


def session(client, interpreter):
    while True:
        target = interpreter.target
        if target.rsp.running:
            ready, _, _ = select.select(
                [client, target.rsp.socket], [], [], 0.05
            )
            if target.rsp.socket in ready:
                target.rsp.poll()
                if not target.rsp.running and target.cable.get(0xF0, 0) & 2:
                    client.sendall(b"\x04\x00\x01\x00")
            if client not in ready:
                continue
        header = receive(client, 3)
        size = int.from_bytes(header[:2], "little")
        if size < 4 or size > 65535 or header[2] != 0:
            raise ValueError("invalid DTL frame")
        raw = receive(client, size - 3)
        try:
            if not raw.endswith(b"\0"):
                raise ValueError("missing terminator")
            script = decode_script(raw[:-1])
            logging.debug("DTL %s", script)
            result = interpreter.execute(script)
            payload = (
                b"00"
                + f"{len(result):04X}".encode()
                + result.hex().upper().encode()
                + b"\0"
            )
            logging.debug("result %s", payload)
        except (ValueError, RuntimeError) as error:
            logging.error("DTL failed: %s (%r)", error, raw)
            payload = b"01\0"
        client.sendall(
            (len(payload) + 3).to_bytes(2, "little") + b"\0" + payload
        )


def scan_device(server, port, stop, name="QEMU-eZ80F91"):
    """Nexus EthernetSCScan protocol: UDP scan -> 100,name,MAC,TCP-port."""
    mac = f"02:5A:44:49:{port >> 8:02X}:{port & 255:02X}"
    reply = f"100,{name},{mac},{port}".encode("ascii")
    server.settimeout(0.25)
    while not stop.is_set():
        try:
            packet, address = server.recvfrom(512)
        except socket.timeout:
            continue
        if packet.rstrip(b"\0") == b"scan":
            server.sendto(reply, address)
            logging.info("Scan device: %s -> %s:%d", address, name, port)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--listen", help="Bind address; scan mode defaults to 0.0.0.0"
    )
    parser.add_argument("--port", type=int, default=4040)
    parser.add_argument("--gdb-host", default="127.0.0.1")
    parser.add_argument("--gdb-port", type=int, default=1234)
    parser.add_argument("--gdb-socket", help="Private QEMU GDB Unix socket")
    parser.add_argument(
        "--scan-dev",
        action="store_true",
        help="Enable SDK-compatible discovery on UDP 3000",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Resume QEMU after the debugger service is ready",
    )
    parser.add_argument("--name", default="QEMU-eZ80F91")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    args.listen = args.listen or ("0.0.0.0" if args.scan_dev else "127.0.0.1")
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    rsp = RSP(args.gdb_host, args.gdb_port, unix=args.gdb_socket)
    stop = threading.Event()
    discovery = None
    scanner = None
    try:
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((args.listen, args.port))
            server.listen(1)
            if args.scan_dev:
                discovery = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                discovery.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                discovery.bind((args.listen, 3000))
                scanner = threading.Thread(
                    target=scan_device,
                    args=(discovery, args.port, stop, args.name),
                    daemon=True,
                )
                scanner.start()
            if args.run:
                rsp.run()
            logging.info(
                "Smart Cable TCP %s:%d -> QEMU %s",
                args.listen,
                args.port,
                args.gdb_socket or f"{args.gdb_host}:{args.gdb_port}",
            )
            while True:
                client, address = server.accept()
                logging.info("ZDS connected: %s", address)
                with client:
                    target = ZDI(rsp)
                    try:
                        session(client, DTL(target))
                    except EOFError:
                        pass
                    except (ConnectionError, OSError, ValueError):
                        logging.exception("connection failed")
                rsp.stop()
                target.sync_breakpoints(0)
    finally:
        stop.set()
        if scanner:
            scanner.join(timeout=1)
        if discovery:
            discovery.close()
        rsp.socket.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
