# Origins and licensing notices

This workspace combines independent projects and test artifacts. It does not
replace their license files or source notices with a blanket workspace license.

| Component | Origin and authoritative notices |
| --- | --- |
| QEMU/eZ80 integration | Pinned [QEMU base](qemu-base.md), upstream license files and per-file SPDX/source notices |
| CAMELF91_24 | [Project](https://github.com/notwendig/CAMELF91_24), `LICENSE`, original `ReadMe.txt` and source headers; the original has specific CamelForth usage conditions |
| ez80f91bsp | [Project](https://github.com/notwendig/ez80f91bsp) and existing source notices; no additional license grant is asserted |
| FreeRTOS-eZ80f91 | [Project](https://github.com/notwendig/FreeRTOS-eZ80f91), port notices and dependency licenses |
| Kernel / Plus-TCP / uzlib | Respective upstream licenses; versions and patches in the [build guide](../subprojects/FreeRTOS-eZ80f91/BUILD.md) |
| ZDS II / Nexus SDK / ZTP | Separately installed vendor packages under their own terms; no SDK copy is included |

[Sources](sources.md) lists technical references. Local vendor PDFs may reside
outside the repository and are not required to exist after cloning. Original
copyright and CamelForth usage notices are preserved; English maintenance guides
do not supersede them.

`examples/` deliberately includes selected generated fixtures with provenance
and hashes. Large SDK applications are instead built from the local installation
into ignored `build/` directories.
