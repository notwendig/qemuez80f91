#!/usr/bin/env python3
"""Apply the reviewed optional FreeRTOS integration to the CAMEL24 checkout."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def prepare(source):
    patch = ROOT / 'examples/camelf91/freertos-core.patch'
    def apply(*options):
        return subprocess.run(['git', '-C', str(source), 'apply', *options, str(patch)],
                              capture_output=True, text=True)
    if apply('--reverse', '--check').returncode == 0:
        print('CAMEL24 FreeRTOS integration already applied.')
        return
    check = apply('--check')
    if check.returncode:
        raise RuntimeError('CAMEL24 has conflicting source changes: ' + check.stderr)
    result = apply('--whitespace=nowarn')
    if result.returncode:
        raise RuntimeError(result.stderr)
    print('CAMEL24 FreeRTOS integration applied.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'subprojects/CAMELF91_24')
    prepare(parser.parse_args().source.resolve())
