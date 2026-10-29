#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
zds_home=${ZDS_HOME:-"$HOME/.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5"}
wine_prefix=${WINEPREFIX:-"$HOME/.wine"}
command_file="$script_dir/build/ztp-demo-zds/open-debug.cmd"
if [ ! -f "$zds_home/bin/Zds2Ide.exe" ]; then
    echo "ZDS II nicht gefunden; ZDS_HOME setzen: $zds_home" >&2
    exit 1
fi
if [ ! -f "$command_file" ]; then
    echo "ZTP-Debugprojekt fehlt: $command_file (siehe docs/ztp-tcpudp.md)" >&2
    exit 1
fi
exec env WINEPREFIX="$wine_prefix" WINEDEBUG=-all wine "$zds_home/bin/Zds2Ide.exe" "@Z:$command_file"
