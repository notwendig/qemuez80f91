#!/bin/sh
# Keep the caller's directory: persistent flash and disks belong there.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export EZ80_PLATFORM_ROOT="$root"
if [ -n "${EZ80_PLATFORM_TOOLS:-}" ]; then
    binary=$EZ80_PLATFORM_TOOLS
elif [ -x "$root/install/bin/ez80-platform" ]; then
    binary=$root/install/bin/ez80-platform
else
    binary=$root/build/platform-tools/tools/qt/ez80-platform
fi
if [ ! -x "$binary" ]; then
    echo "Qt-6-Plattformtools fehlen. Im Projektverzeichnis ausführen:" >&2
    echo "  cmake -S . -B build/platform-tools -G Ninja" >&2
    echo "  cmake --build build/platform-tools" >&2
    exit 1
fi
exec "$binary" "$@"
