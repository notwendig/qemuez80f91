#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
# Keep setup scoped to CAMEL and its public BSP dependency.
git -C "$root" submodule update --init -- subprojects/CAMELF91_24
actual=$(git -C "$root/subprojects/CAMELF91_24" rev-parse HEAD)
expected=b975f3acac08c70c05d951aad22e5c1824446206
if ! git -C "$root/subprojects/CAMELF91_24" merge-base --is-ancestor "$expected" "$actual"; then
    echo "Expected CAMELF91_24 based on $expected; found $actual" >&2
    exit 1
fi
git -C "$root/subprojects/CAMELF91_24" submodule update --init -- libbsp
echo "CAMELF91_24 ready at $actual"
