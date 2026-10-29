# SPDX-License-Identifier: GPL-2.0-or-later
"""Subset of the Smart Cable DTL language used by Zilog eZ80 algorithms.

No Python eval: expressions and statements are parsed explicitly. Unknown syntax
fails the request instead of acknowledging an operation that was not performed.
"""

import re


class DTLError(ValueError):
    pass


TOKEN = re.compile(
    r'\s+|"[0-9a-fA-F]*"|[RV][0-9A-Fa-f]{2}|[0-9A-Fa-f]+'
    r'|\+\+|--|<<|>>|<=|>=|==|!=|&&|\|\||.'
)
OPS = {
    "||": 1,
    "&&": 2,
    "|": 3,
    "^": 4,
    "&": 5,
    "==": 6,
    "!=": 6,
    "<": 7,
    ">": 7,
    "<=": 7,
    ">=": 7,
    "<<": 8,
    ">>": 8,
    "+": 9,
    "-": 9,
    "*": 10,
    "/": 10,
    "%": 10,
}


class DTL:
    def __init__(self, target):
        self.target = target
        self.variables = [0] * 256
        self.buffer = bytearray()
        self.steps = 0

    def take(self, expected=None):
        if self.pos >= len(self.tokens):
            raise DTLError("unexpected end")
        token = self.tokens[self.pos]
        if expected is not None and token != expected:
            raise DTLError(f"expected {expected}, got {token}")
        self.pos += 1
        return token

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ""

    def expr(self, minimum=0):
        token = self.take()
        if token in ("!", "~", "-", "+"):
            a = self.expr(11)
            value = {
                "!": lambda: int(not a),
                "~": lambda: ~a,
                "-": lambda: -a,
                "+": lambda: a,
            }[token]()
        elif token == "(":
            value = self.expr()
            self.take(")")
        elif token == "[":
            start = self.expr()
            if self.peek() == ":":
                self.take()
                count = self.expr()
                self.take("]")
                value = bytes(self.buffer[start : start + count])
            else:
                self.take("]")
                if not 0 <= start < len(self.buffer):
                    raise DTLError(f"buffer index {start}")
                value = self.buffer[start]
        elif token == "@":
            value = len(self.buffer)
        elif re.fullmatch("V[0-9A-Fa-f]{2}", token):
            index = int(token[1:], 16)
            value = self.variables[index]
            if self.peek() in ("++", "--"):
                self.variables[index] += 1 if self.take() == "++" else -1
        elif re.fullmatch("R[0-9A-Fa-f]{2}", token):
            value = self.target.read(int(token[1:], 16))
        elif token.startswith('"'):
            value = bytes.fromhex(token[1:-1])
        elif re.fullmatch("[0-9A-Fa-f]+", token):
            value = int(token, 16)
        else:
            raise DTLError(f"invalid expression {token}")
        while self.peek() in OPS and OPS[self.peek()] >= minimum:
            op = self.take()
            right = self.expr(OPS[op] + 1)
            if isinstance(value, bytes) or isinstance(right, bytes):
                raise DTLError("arithmetic on byte buffer")
            operations = {
                "+": lambda: value + right,
                "-": lambda: value - right,
                "*": lambda: value * right,
                "/": lambda: value // right,
                "%": lambda: value % right,
                "<<": lambda: value << right,
                ">>": lambda: value >> right,
                "&": lambda: value & right,
                "|": lambda: value | right,
                "^": lambda: value ^ right,
                "==": lambda: int(value == right),
                "!=": lambda: int(value != right),
                "<": lambda: int(value < right),
                ">": lambda: int(value > right),
                "<=": lambda: int(value <= right),
                ">=": lambda: int(value >= right),
                "&&": lambda: int(bool(value) and bool(right)),
                "||": lambda: int(bool(value) or bool(right)),
            }
            value = operations[op]()
        if minimum == 0 and self.peek() == "?":
            self.take()
            yes = self.expr()
            self.take(":")
            no = self.expr()
            value = yes if value else no
        return value

    def block(self, end=None):
        while self.pos < len(self.tokens) and self.peek() != end:
            self.steps += 1
            if self.steps > 100000:
                raise DTLError("instruction limit")
            token = self.take()
            if token == ".":
                self.buffer.clear()
            elif token == "#":
                # GET_EMUL_CONFIG: firmware major/minor, capability byte,
                # then the transport buffer size in big-endian order. The
                # DLL derives its block sizes from this advertised limit.
                self.buffer.extend(self.target.configuration())
            elif token == "$":
                self.output.extend(self.buffer)
            elif token == "_":
                self.expr()  # Firmware delay; virtual target needs none.
            elif token == "\\":
                if self.expr():
                    return True
            elif token == "{":
                count = None if self.peek() == ":" else self.expr()
                self.take(":")
                start = self.pos
                depth = 1
                finish = start
                while finish < len(self.tokens) and depth:
                    if self.tokens[finish] == "{":
                        depth += 1
                    if self.tokens[finish] == "}":
                        depth -= 1
                    finish += 1
                if depth:
                    raise DTLError("unclosed loop")
                for _ in range(100000 if count is None else count):
                    self.pos = start
                    if self.block("}"):
                        break
                else:
                    if count is None:
                        raise DTLError("unbounded loop")
                self.pos = finish
            elif token == "[":
                index = None if self.peek() == "]" else self.expr()
                count = None
                if self.peek() == ":":
                    self.take()
                    count = self.expr()
                self.take("]")
                self.take("=")
                if count is not None:
                    start = self.pos
                    # The shipped memory-read algorithms repeat a bare R20.
                    # Batch that stream while preserving all other expression
                    # side effects through the normal interpreter path.
                    if self.peek() == "R20" and hasattr(self.target, "read_block"):
                        following = self.tokens[self.pos + 1] if self.pos + 1 < len(self.tokens) else ""
                        if following not in OPS and following not in ("?", "++", "--"):
                            self.take()
                            raw = self.target.read_block(0x20, count)
                            if index + count > len(self.buffer):
                                self.buffer.extend(bytes(index + count - len(self.buffer)))
                            self.buffer[index:index + count] = raw
                            continue
                    for offset in range(count):
                        self.pos = start
                        value = self.expr()
                        position = index + offset
                        if position >= len(self.buffer):
                            self.buffer.extend(
                                bytes(position - len(self.buffer) + 1)
                            )
                        self.buffer[position] = value & 255
                    continue
                value = self.expr()
                raw = (
                    value if isinstance(value, bytes) else bytes([value & 255])
                )
                if index is None:
                    self.buffer.extend(raw)
                else:
                    if not 0 <= index < len(self.buffer):
                        raise DTLError("buffer write out of range")
                    self.buffer[index : index + len(raw)] = raw
            elif re.fullmatch("[RV][0-9A-Fa-f]{2}", token):
                self.take("=")
                value = self.expr()
                index = int(token[1:], 16)
                if token[0] == "V":
                    self.variables[index] = value
                else:
                    self.target.write(index, value)
            else:
                raise DTLError(f"unknown statement {token}")
        return False

    def execute(self, script):
        self.tokens = [t for t in TOKEN.findall(script) if not t.isspace()]
        self.pos = 0
        self.steps = 0
        self.output = bytearray()
        self.block()
        return bytes(self.output)
