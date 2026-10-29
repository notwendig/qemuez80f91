#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
qemu_dir=${1:-"$root/qemu"}
base=4fc49f46dc95d4a27de2509e7fceb2931e91faeb
actual=$(git -C "$qemu_dir" rev-parse HEAD)
if [ "$actual" != "$base" ]; then
    echo "Expected QEMU base $base; found $actual" >&2
    exit 1
fi
patch="$root/patches/0001-ez80f91-minimal.patch"
if git -C "$qemu_dir" apply --reverse --check "$patch" 2>/dev/null; then
    echo "eZ80F91 patch already applied"
    exit 0
fi
git -C "$qemu_dir" apply --check "$patch"
git -C "$qemu_dir" apply "$patch"
echo "Applied eZ80F91 patch"
