#!/bin/sh
# Start the eZ80F91 from its persistent flash in the current directory.
set -eu

usage() {
    echo "Aufruf: $0 [--run] [--kit] [--headless] [--bridge <Name|none>] [--hostname <Name>] [--wd2797a <Basisport>] [--dev <Verzeichnis>] [--fs-root <Unix-Verzeichnis>] [dbgport <port>]"
    echo "Standard: Debugport 4040; QEMU_EZ80 wählt die QEMU-Datei."
}

port=4040
run=
kit=
dev=
fs_root=
devport=0x1000
hostname=
bridge=br0
headless=
while [ $# -gt 0 ]; do
    case "$1" in
        --run) run=--run; shift ;;
        --kit) kit=--kit; shift ;;
        --headless|--session) headless=--headless; shift ;;
        --bridge) [ $# -ge 2 ] && [ -n "$2" ] || { usage >&2; exit 2; }; bridge=$2; shift 2 ;;
        --hostname) [ $# -ge 2 ] && [ -n "$2" ] || { usage >&2; exit 2; }; hostname=$2; shift 2 ;;
        --dev) [ $# -ge 2 ] || { usage >&2; exit 2; }; dev=$2; shift 2 ;;
        --fs-root) [ $# -ge 2 ] || { usage >&2; exit 2; }; fs_root=$2; shift 2 ;;
        --wd2797a|--devport) [ $# -ge 2 ] || { usage >&2; exit 2; }; devport=$2; shift 2 ;;
        *) break ;;
    esac
done
case $# in
    0) ;;
    1) case "$1" in -h|--help) usage; exit 0 ;; *) usage >&2; exit 2 ;; esac ;;
    2) [ "$1" = dbgport ] || { usage >&2; exit 2; }; port=$2 ;;
    *) usage >&2; exit 2 ;;
esac
case "$port" in
    ''|*[!0-9]*) echo 'Debugport muss zwischen 1 und 65535 liegen.' >&2; exit 2 ;;
esac
# Strip leading zeroes before numerical comparison.
while [ "${port#0}" != "$port" ]; do port=${port#0}; done
if [ ${#port} -gt 5 ] || [ -z "$port" ] || [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
    echo 'Debugport muss zwischen 1 und 65535 liegen.' >&2
    exit 2
fi
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -x "$script_dir/install/bin/qemu-system-ez80" ]; then
    default_qemu=$script_dir/install/bin/qemu-system-ez80
elif [ -x "$script_dir/build/ez80/qemu-system-ez80" ]; then
    default_qemu=$script_dir/build/ez80/qemu-system-ez80
else
    default_qemu=/tmp/qemuez80f91-build-baseline/qemu-system-ez80
fi
qemu=${QEMU_EZ80:-$default_qemu}
if [ ! -x "$qemu" ]; then
    echo "QEMU nicht ausführbar: $qemu (QEMU_EZ80 setzen)." >&2
    exit 1
fi
set -- start --port "$port" --qemu "$qemu" --wd2797a "$devport" --bridge "$bridge"
[ -z "$run" ] || set -- "$@" "$run"
[ -z "$kit" ] || set -- "$@" "$kit"
[ -z "$dev" ] || set -- "$@" --dev "$dev"
[ -z "$fs_root" ] || set -- "$@" --fs-root "$fs_root"
[ -z "$hostname" ] || set -- "$@" --hostname "$hostname"
[ -z "$headless" ] || set -- "$@" "$headless"
exec "$script_dir/tools/platform.sh" "$@"
