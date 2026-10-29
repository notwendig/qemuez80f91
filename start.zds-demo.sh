#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec env WINEPREFIX=/home/juergen/.wine WINEDEBUG=-all wine /home/juergen/.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5/bin/Zds2Ide.exe "@Z:${script_dir}/build/ztp-demo-zds/open-debug.cmd"
