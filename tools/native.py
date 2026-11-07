"""Temporary command compatibility for callers of the former Python UIs."""
import os
from pathlib import Path


def execute(command, arguments):
    launcher = Path(__file__).resolve().with_name('platform.sh')
    os.execv(str(launcher), [str(launcher), command, *arguments])
