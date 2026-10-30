# SPDX-License-Identifier: GPL-2.0-or-later
"""eZ80F91 ZDI registers backed by QEMU's stopped CPU and port space."""

from dtl import DTLError


class ZDI:
    def __init__(self, rsp):
        self.rsp = rsp
        self.cable = {0xEC: 1, 0xEE: 1, 0xEF: 1}
        self.wr = bytearray(256)
        self.rd = bytearray(3)
        self.break_control = 0x80
        self.breakpoints = set()
        self.prefetch = True

    def configuration(self):
        # The EthernetSC DLL receives at most 0x2100 bytes per frame.
        # Advertise 0x2000 so its hex-encoded replies fit that buffer.
        return bytes([1, 1, 0, 0x20, 0])

    def read(self, address):
        if address >= 0xEA:
            return self.cable.get(address, 0)
        if address in (0, 1, 2):
            return (8, 0, 1)[address]
        if address == 3:
            # A running target can stop on one of the hardware breakpoints.
            self.rsp.poll()
            if self.rsp.running:
                return 0
            r = self.rsp.registers()
            return 0x80 | (r[18] << 4) | (r[19] << 3) | (r[20] << 2)
        if 0x10 <= address <= 0x12:
            return self.rd[address - 0x10]
        if address == 0x20:
            r = self.rsp.registers()
            pc = r[0]
            value = 0 if self.prefetch else self.rsp.memory(pc, 1)[0]
            self.prefetch = False
            r[0] = (pc + 1) & 0xFFFFFF
            self.rsp.set_registers(r)
            return value
        raise DTLError(f"unsupported ZDI read {address:02x}")

    def read_block(self, address, count):
        """Read the ZDI memory stream with its initial prefetch byte."""
        if address != 0x20:
            return bytes(self.read(address) for _ in range(count))
        if not count:
            return b""
        r = self.rsp.registers()
        pc = r[0]
        result = bytearray()
        if self.prefetch:
            result.append(0)
            pc = (pc + 1) & 0xFFFFFF
            self.prefetch = False
        while len(result) < count:
            length = min(count - len(result), 1024, 0x1000000 - pc)
            result.extend(self.rsp.memory(pc, length))
            pc = (pc + length) & 0xFFFFFF
        r[0] = pc
        self.rsp.set_registers(r)
        return bytes(result)

    def write(self, address, value):
        if address >= 0xEA:
            self.cable[address] = (
                int.from_bytes(value, "big")
                if isinstance(value, bytes)
                else value
            )
            return
        if address == 0x30:
            raw = value if isinstance(value, bytes) else bytes([value & 255])
            r = self.rsp.registers()
            self.rsp.write_memory(r[0], raw)
            r[0] = (r[0] + len(raw)) & 0xFFFFFF
            self.rsp.set_registers(r)
            return
        value &= 255
        self.wr[address] = value
        if address == 0x10:
            self.break_control = value
            if value & 0x80:
                self.rsp.stop()
                if value & 1:
                    self.rsp.step()
            else:
                self.sync_breakpoints(value)
                if not self.rsp.running:
                    self.rsp.run()
        elif address == 0x11 and value & 0x80:
            self.rsp.stop(force=True)
            reply = self.rsp.command("qRcmd," + b"system_reset".hex())
            while reply.startswith("O") and reply != "OK":
                reply = self.rsp.packet()
        elif address == 0x16:
            # The shipped GET_REGS_ALL Algo16 uses R16=16 to recover MBASE
            # before restoring AF. This is a Nexus algorithm compatibility
            # alias for Read AF, not an additional silicon ZDI command.
            if value == 0x16:
                value = 0
            r = self.rsp.registers()
            if value in (8, 9):
                r[18] = int(value == 8)
            elif value == 10:
                for a, b in ((1, 6), (2, 7), (3, 8), (12, 14), (13, 15)):
                    r[a], r[b] = r[b], r[a]
            elif value & 0x7F <= 7:
                which = value & 7
                index = (None, 1, 2, 3, 4, 5, 9 if r[18] else 10, 0)[which]
                if value & 0x80:
                    v = int.from_bytes(self.wr[0x13:0x16], "little")
                    if which == 0:
                        r[12], r[13], r[17] = (
                            v & 255,
                            (v >> 8) & 255,
                            (v >> 16) & 255,
                        )
                    else:
                        r[index] = v
                        if which == 7:
                            self.prefetch = True
                else:
                    v = (
                        r[12] | r[13] << 8 | r[17] << 16
                        if which == 0
                        else r[index]
                    )
                    if which == 7 and not self.prefetch:
                        # ZDI reports the CPU's two-byte instruction prefetch
                        # ahead of the memory stream. The shipped split-read
                        # algorithms subtract three, then discard one dummy
                        # byte after writing PC for the next block.
                        v = (v + 2) & 0xFFFFFF
                    self.rd[:] = v.to_bytes(3, "little")
            else:
                raise DTLError(f"ZDI RW control {value:02x}")
            self.rsp.set_registers(r)
        elif address == 0x25:
            self.inject()
        elif (
            address <= 0x0F
            or 0x13 <= address <= 0x15
            or 0x21 <= address <= 0x24
        ):
            pass  # Write-only ZDI latch.
        else:
            raise DTLError(f"unsupported ZDI write {address:02x}")

    def sync_breakpoints(self, control):
        points = {
            int.from_bytes(self.wr[i * 4 : i * 4 + 3], "little")
            for i in range(4)
            if control & (8 << i)
        }
        for address in self.breakpoints - points:
            if self.rsp.command(f"z0,{address:x},1") != "OK":
                raise DTLError("clear breakpoint")
        for address in points - self.breakpoints:
            if self.rsp.command(f"Z0,{address:x},1") != "OK":
                raise DTLError("set breakpoint")
        self.breakpoints = points

    def inject(self):
        r = self.rsp.registers()
        op, second, third = self.wr[0x25], self.wr[0x24], self.wr[0x23]
        if op == 0x3E:
            r[12] = second
        elif op == 0xF3:
            r[20] = r[21] = 0
        elif op == 0xFB:
            r[20] = r[21] = 1
        elif op == 3:
            r[1] = (r[1] + 1) & (0xFFFFFF if r[18] else 0xFFFF)
        elif op == 0xED:
            if second in (0x38, 0x78):
                port = third if second == 0x38 else r[1] & 0xFFFF
                r[12] = self.rsp.memory(0x1000000 + port, 1)[0]
            elif second in (0x39, 0x79):
                port = third if second == 0x39 else r[1] & 0xFFFF
                self.rsp.write_memory(0x1000000 + port, bytes([r[12]]))
            elif second == 0x4F:
                r[16] = r[12]
            elif second == 0x5F:
                r[12] = r[16]
                r[13] = (
                    (r[13] & 1)
                    | (r[12] & 0x80)
                    | (0x40 if not r[12] else 0)
                    | (r[21] << 2)
                )
            elif second == 0xD7:
                r[3] = r[11]
                r[13] = (
                    (r[13] & 1)
                    | (0x80 if r[11] & 0x8000 else 0)
                    | (0x40 if not r[11] else 0)
                    | (r[21] << 2)
                )
            elif second == 0xC7:
                r[11] = r[3] & 0xFFFF
            elif second == 0x6D:
                r[17] = r[12]
            elif second == 0x6E:
                r[12] = r[17]
            elif second in (0x7D, 0x7E):
                r[19] = int(second == 0x7D)
            else:
                raise DTLError(f"unsupported injected ED {second:02x}")
        else:
            raise DTLError(f"unsupported injected opcode {op:02x}")
        self.rsp.set_registers(r)
