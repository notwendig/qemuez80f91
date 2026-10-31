#!/bin/sh
# Start the eZ80F91 from its persistent flash in the current directory.
set -eu

usage() {
    echo "Aufruf: $0 [--run] [--kit] [--hostname <Name>] [--wd2797a <Basisport>] [--dev <Verzeichnis>] [dbgport <port>]"
    echo "Standard: Debugport 4040; QEMU_EZ80 wählt die QEMU-Datei."
}

port=4040
run=
kit=
dev=
devport=0x1000
hostname=
while [ $# -gt 0 ]; do
    case "$1" in
        --run) run=--run; shift ;;
        --kit) kit=--kit; shift ;;
        --hostname) [ $# -ge 2 ] && [ -n "$2" ] || { usage >&2; exit 2; }; hostname=$2; shift 2 ;;
        --dev) [ $# -ge 2 ] || { usage >&2; exit 2; }; dev=$2; shift 2 ;;
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
set -- --launch "$port" "$qemu" --wd2797a "$devport"
[ -z "$run" ] || set -- "$@" "$run"
[ -z "$kit" ] || set -- "$@" "$kit"
[ -z "$dev" ] || set -- "$@" --dev "$dev"
[ -z "$hostname" ] || set -- "$@" --hostname "$hostname"
exec python3 "$script_dir/tools/start.py" "$@"
