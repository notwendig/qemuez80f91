"""Compatibility entry point for the native Qt 6 demo tool."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.native import execute

if __name__ == '__main__':
    execute('demo', sys.argv[1:])
