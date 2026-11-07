#!/usr/bin/env python3
"""Install the built emulator and a launcher for this project checkout."""
import argparse
from pathlib import Path
import shlex
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, default=ROOT / 'install')
    parser.add_argument('--qemu', type=Path, default=ROOT / 'build/ez80/qemu-system-ez80')
    parser.add_argument('--platform-tools', type=Path,
                        default=ROOT / 'build/platform-tools/tools/qt/ez80-platform')
    args = parser.parse_args()
    source = args.qemu.resolve(strict=True)
    native_source = args.platform_tools.resolve(strict=True)
    bindir = args.prefix.resolve() / 'bin'
    bindir.mkdir(parents=True, exist_ok=True)
    target = bindir / 'qemu-system-ez80'
    # Replace atomically so an already running emulator keeps its executable.
    with tempfile.NamedTemporaryFile(dir=bindir, delete=False) as output:
        staged = Path(output.name)
    try:
        shutil.copyfile(source, staged)
        staged.chmod(0o755)
        staged.replace(target)
    finally:
        staged.unlink(missing_ok=True)
    native_target = bindir / 'ez80-platform'
    with tempfile.NamedTemporaryFile(dir=bindir, delete=False) as output:
        staged = Path(output.name)
    try:
        shutil.copyfile(native_source, staged)
        staged.chmod(0o755)
        staged.replace(native_target)
    finally:
        staged.unlink(missing_ok=True)
    launcher = bindir / 'qemuez80f91'
    launcher.write_text('#!/bin/sh\nset -eu\n'
                        f'export QEMU_EZ80={shlex.quote(str(target))}\n'
                        f'export EZ80_PLATFORM_TOOLS={shlex.quote(str(native_target))}\n'
                        f'exec {shlex.quote(str(ROOT / "start.sh"))} "$@"\n')
    launcher.chmod(0o755)
    print(f'Emulator: {target}\nQt tools: {native_target}\nStarter:  {launcher}')


if __name__ == '__main__':
    main()
