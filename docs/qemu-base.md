# QEMU base

## Pinned source

| Property | Value |
| --- | --- |
| Upstream | `https://gitlab.com/qemu-project/qemu.git` |
| Release | `v11.1.2` |
| Base commit | `4fc49f46dc95d4a27de2509e7fceb2931e91faeb` |
| System target | `ez80-softmmu` |
| CPU | `ez80f91` |
| Machines | `ez80f91-minimal`, `ez80f91-freertos` |
| Complete local changes | `patches/0001-ez80f91-minimal.patch` |

`qemu/` is an ignored, independent repository. It may contain a development
branch; its upstream remote is not this project's publication destination.
The full eZ80 implementation is distributed as the workspace patch.

## Reproduction

```sh
git clone --depth 1 --branch v11.1.2 https://gitlab.com/qemu-project/qemu.git qemu
sh scripts/apply-qemu-patches.sh
mkdir -p build/ez80
cd build/ez80
../../qemu/configure --target-list=ez80-softmmu --disable-docs --disable-werror --without-default-features --enable-tcg --enable-system --disable-tools
ninja -j8 qemu-system-ez80
./qemu-system-ez80 --version
```

Initial configuration may download pinned build subprojects and Python packages.
`--disable-download` works only after they are available. Resolve configure
errors before compilation; do not import arbitrary files from other QEMU releases.

The patch script verifies the base and accepts an identical applied patch.
See [Development](development.md) for existing development copies. Keep build
directories outside the source tree.

## Integration and limits

`target/ez80/` contains registers, decoding, TCG and GDB support; `hw/ez80/`
contains the machines and F91 devices. Kconfig/Meson register the target.
Host-side 32-bit storage does not change architectural 8/16/24-bit widths.

A translation block currently executes one decoded guest instruction. This
is a functional implementation, not a model of instruction-cycle timings or
electrical buses. The original AVR build was only a toolchain check.

The development build uses GCC, Python, Ninja, pkg-config and GLib; configure
reports actual host versions. `/tmp/qemuez80f91-build-baseline` is a historical
local path, not a prerequisite. Set `QEMU_EZ80` to your own build.
See [Architecture](architecture.md), [Status](status.md) and [Testing](testing.md).
