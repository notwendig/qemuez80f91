#!/usr/bin/env python3
"""Initialize firmware submodules and apply their pinned compatibility patches."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    run('git', '-C', str(ROOT), 'submodule', 'update', '--init', '--',
        'subprojects/CAMELF91_24', 'subprojects/FreeRTOS-eZ80f91')
    run('git', '-C', str(ROOT / 'subprojects/CAMELF91_24'),
        'submodule', 'update', '--init', '--', 'libbsp')
    project = ROOT / 'subprojects/FreeRTOS-eZ80f91'
    run(sys.executable, str(project / 'setup-dependencies.py'))
    required = (
        ROOT / 'subprojects/CAMELF91_24/libbsp/libbsp.zdsproj',
        project / 'kernel/include/FreeRTOS.h',
        project / 'network/source/portable/BufferManagement/BufferAllocation_2.c',
        project / 'uzlib/src/adler32.c',
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError('Incomplete dependency setup: ' + ', '.join(missing))
    print('Firmware dependencies ready. Open the ZDS project and select Rebuild All.')


if __name__ == '__main__':
    main()
