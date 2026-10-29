#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
# Deliberately do not recurse: the test uses the local polling adapter.
git -C "$root" submodule update --init -- subprojects/CAMELF91_24
actual=$(git -C "$root/subprojects/CAMELF91_24" rev-parse HEAD)
expected=b975f3acac08c70c05d951aad22e5c1824446206
if [ "$actual" != "$expected" ]; then
    echo "Expected CAMELF91_24 $expected; found $actual" >&2
    exit 1
fi
echo "CAMELF91_24 ready at $actual"
