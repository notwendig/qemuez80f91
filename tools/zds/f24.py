"""Compatibility entry point for the native Qt 6 f24 tool."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.native import execute

if __name__ == '__main__':
    execute('f24', sys.argv[1:])
