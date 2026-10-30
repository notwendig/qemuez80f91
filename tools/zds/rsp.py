# SPDX-License-Identifier: GPL-2.0-or-later
"""Small synchronous GDB remote client for the local QEMU debug endpoint."""

import socket
import select


class RSP:
    def __init__(self, host=None, port=None, unix=None):
        if unix:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect(unix)
        else:
            self.socket = socket.create_connection((host, port), timeout=10)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.running = False
        self.command("?")

    def packet(self):
        while True:
            marker = self.socket.recv(1)
            if not marker:
                raise ConnectionError("QEMU disconnected")
            if marker == b"$":
                break
        data = bytearray()
        while True:
            c = self.socket.recv(1)
            if not c:
                raise ConnectionError("QEMU disconnected")
            if c == b"#":
                break
            data.extend(c)
        check = bytearray()
        while len(check) < 2:
            chunk = self.socket.recv(2 - len(check))
            if not chunk:
                raise ConnectionError("QEMU disconnected")
            check.extend(chunk)
        if int(check, 16) != sum(data) & 255:
            raise ConnectionError("RSP checksum")
        self.socket.sendall(b"+")
        return data.decode("ascii")

    def command(self, command):
        raw = command.encode("ascii")
        self.socket.sendall(
            b"$" + raw + b"#" + f"{sum(raw) & 255:02x}".encode()
        )
        reply = self.packet()
        # An out-of-band interrupt can precede a command reply when QMP
        # resumed the CPU independently of this RSP connection.
        while command not in ("?", "s") and reply.startswith(("T", "S")):
            reply = self.packet()
        return reply

    def poll(self):
        if self.running and select.select([self.socket], [], [], 0)[0]:
            self.packet()
            self.running = False

    def stop(self, force=False):
        self.poll()
        if force and not self.running:
            self.socket.sendall(b"\x03")
            self.command("?")
        elif self.running:
            self.socket.sendall(b"\x03")
            self.packet()
            self.running = False

    def registers(self):
        self.stop()
        raw = bytes.fromhex(self.command("g"))
        if len(raw) != 96:
            raise RuntimeError("QEMU needs the eZ80 GDB register patch")
        return [
            int.from_bytes(raw[i : i + 4], "little") for i in range(0, 96, 4)
        ]

    def set_registers(self, values):
        self.stop()
        if (
            self.command(
                "G" + b"".join(v.to_bytes(4, "little") for v in values).hex()
            )
            != "OK"
        ):
            raise RuntimeError("register write failed")

    def memory(self, address, count):
        self.stop()
        reply = self.command(f"m{address:x},{count:x}")
        if reply.startswith("E"):
            raise RuntimeError(f"unmapped memory at {address:06x}: {reply}")
        return bytes.fromhex(reply)

    def write_memory(self, address, data):
        self.stop()
        # QEMU's GDB packet buffer is bounded; ZDS sends RAM test and loader
        # buffers of several KiB. Keep the hex payload below that limit.
        for offset in range(0, len(data), 1024):
            chunk = data[offset:offset + 1024]
            if self.command(f"M{address + offset:x},{len(chunk):x}:" + chunk.hex()) != "OK":
                raise RuntimeError("memory write failed")

    def step(self):
        self.stop()
        reply = self.command("s")
        if not reply.startswith(("T", "S")):
            raise RuntimeError(f"step: {reply}")

    def run(self):
        self.socket.sendall(b"$c#63")
        if self.socket.recv(1) != b"+":
            raise ConnectionError("QEMU rejected continue")
        self.running = True
