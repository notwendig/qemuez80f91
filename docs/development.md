# Development and repository maintenance

## Repository layout

| Path | Ownership and purpose |
| --- | --- |
| `docs/` | Maintained English guides, architecture and implementation evidence |
| `patches/0001-ez80f91-minimal.patch` | Complete QEMU changes relative to the pinned base |
| `qemu/` | Ignored local QEMU repository; export its changes into the patch |
| `subprojects/CAMELF91_24/` | Independent submodule with nested `libbsp/` |
| `subprojects/FreeRTOS-eZ80f91/` | Independent submodule with kernel, TCP/IP and uzlib dependencies |
| `examples/` | Reproduction sources and deliberately tracked test images |
| `tests/` | Directly executable scripts; requirements in the test catalog |
| `tools/`, `scripts/` | Launchers, debugger bridge and build/setup tools |
| `build/` | Ignored generated files and reports |

## Updating QEMU

The base is `4fc49f46dc95d4a27de2509e7fceb2931e91faeb`. Local development
commits are allowed. Export the complete working-tree state relative to the base:

```sh
git -C qemu diff --binary 4fc49f46dc95d4a27de2509e7fceb2931e91faeb > patches/0001-ez80f91-minimal.patch
git -C qemu apply --reverse --check ../patches/0001-ez80f91-minimal.patch
ninja -C build/ez80 -j8 qemu-system-ez80
```

New QEMU files must be known to its index for `git diff` to include them.
Do not reset unrelated edits. Also check forward application in an unchanged
base checkout. Publish the patch through this project; the configured upstream
QEMU remote is not the destination for these changes.

## Firmware and generated files

CAMEL's shared kit driver is `examples/camelf91/kit.inc`, identical to the
native copy under `subprojects/CAMELF91_24/asm/`. `kit_font.py` generates the
font and `word_tests.py` generates the Forth test file. The builder checks
shared sources and records image/source hashes in `camel.json`. It reads the
corrected CAMEL commit directly; `patches/camelf91/` is no longer required.

FreeRTOS dependency versions and ZDS patches are maintained in the subproject's
[build guide](../subprojects/FreeRTOS-eZ80f91/BUILD.md) and `setup-dependencies.py`.
Use public upstream revisions plus the supplied patches, not unpublished library commits.

Keep fixture `.bin`, `.json` and `.map` files together. They are test inputs,
not disposable build products. SDK output, listings, objects and IDE sessions
belong in ignored build directories.

## Cleanup

Python/lint caches, temporary reports and obsolete build copies can be removed
after checking their purpose. Before removing duplicate checkouts, compare
working trees, HEADs and origins. An unchecked `git clean -xfd` can destroy
SDK files and saved guest flash.

Preserve flash files `ez80f91_*.<port>`, active logs, used ZDS project/target/linker
files, fixtures and metadata, vendor references, original notices and firmware sources.
Historical session notes are available in Git; maintained guides replace them.

## Commit and publication

Publish dependencies before their parents: BSP before CAMEL, library revisions
and patches before the FreeRTOS parent, and firmware projects before the main
repository. Then update the main gitlinks so published commits remain obtainable.

```sh
git status --short
git diff --check
git submodule status --recursive
```

Check [tests](testing.md), documentation links and fixture hashes before a
commit. Stage deliberately; do not publish flash data, SDKs, caches or credentials.
Avoid force pushes and reconcile new remote commits first.
