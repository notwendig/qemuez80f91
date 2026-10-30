#!/usr/bin/env python3
"""Integration smoke tests for the experimental eZ80F91 QEMU target."""
import json
import pathlib
import select
import subprocess
import sys
import tempfile
import time

binary = str(pathlib.Path(sys.argv[1]).resolve())

class VM:
    def __init__(self, rom, serial="none", extra=(),
                 machine="ez80f91-minimal", loader="-bios", pass_fds=(), cwd=None):
        # Ordinary tests must not read or overwrite the caller's saved flash.
        self._workspace = tempfile.TemporaryDirectory(prefix='f91-vm-') if cwd is None else None
        run_cwd = self._workspace.name if self._workspace is not None else cwd
        rom = str(pathlib.Path(rom).resolve())
        self.p = subprocess.Popen([binary, '-M', machine, loader, rom,
                                   '-display', 'none', '-serial', serial, '-monitor', 'none',
                                   '-S', '-qmp', 'stdio', *extra], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=pass_fds, cwd=run_cwd)
        self.buffer = b''
        assert 'QMP' in self.read()
        self.cmd('qmp_capabilities')

    def read(self):
        deadline = time.monotonic() + 10
        while b'\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.p.stdout], [], [], remaining)[0]:
                raise AssertionError('QMP response timeout')
            chunk = self.p.stdout.read1(4096)
            if not chunk:
                raise AssertionError(f'QEMU exited: {self.p.stderr.read().decode()}')
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b'\n', 1)
        return json.loads(line)

    def cmd(self, command, arguments=None):
        msg = {'execute': command}
        if arguments is not None:
            msg['arguments'] = arguments
        self.p.stdin.write(json.dumps(msg).encode() + b'\n')
        self.p.stdin.flush()
        while True:
            reply = self.read()
            if 'event' in reply:
                continue
            assert 'error' not in reply, reply
            return reply['return']

    def hmp(self, command):
        return self.cmd('human-monitor-command', {'command-line': command})

    def halted(self):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if 'HALTED=1' in self.hmp('info registers'):
                return
            time.sleep(0.01)
        raise AssertionError('CPU did not halt')

    def close(self):
        if self.p.poll() is None:
            self.cmd('quit')
        self.p.wait(timeout=5)
        workspace = getattr(self, '_workspace', None)
        if workspace is not None:
            workspace.cleanup()
        assert self.p.returncode == 0, self.p.stderr.read().decode()

