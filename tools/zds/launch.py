"""Compatibility entry point for the native Qt 6 zds-launch tool."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.native import execute

if __name__ == '__main__':
    execute('zds-launch', sys.argv[1:])
