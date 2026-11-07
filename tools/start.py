"""Compatibility entry point; the launcher itself is implemented in C++/Qt 6."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.native import execute

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--session', action='store_true')
    modes.add_argument('--launch', action='store_true')
    parser.add_argument('port')
    parser.add_argument('qemu')
    args, extra = parser.parse_known_args()
    execute('start', ['--port', args.port, '--qemu', args.qemu,
                      *(['--headless'] if args.session else []), *extra])
