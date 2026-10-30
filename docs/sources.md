# Technical references and source versions

## Vendor manuals

- [eZ80F91 MCU Product Specification, PS0192](https://www.zilog.com/docs/ez80acclaim/ps0192.pdf)
- [eZ80 CPU User Manual, UM0077](https://www.zilog.com/docs/um0077.pdf)
- [eZ80F91 Modular Development Kit, UM0170](https://www.zilog.com/docs/ez80acclaim/devtools/um0170.pdf)

The locally used revisions are `../doc/ps0192.pdf` (PS019217-1222) and
`../doc/um0077.pdf` (UM007715-0415). These files need not be present in a clone.
See [F91 baseline](ez80f91-baseline.md) for scope and reset registers.

## Upstream projects

- [QEMU](https://gitlab.com/qemu-project/qemu), pinned as documented in [QEMU base](qemu-base.md).
- [QEMU architectures](https://www.qemu.org/docs/master/about/emulation.html).
- [CEmu](https://github.com/CE-Programming/CEmu), GPLv3: potential CPU reference
  for eZ80 TI calculators, not an F91 SoC model.
- [WilliamTowle/qemu-z80](https://github.com/WilliamTowle/qemu-z80): a separate
  Z80 fork, not evidence of eZ80F91 support.

Record origin, licensing notices and exact revisions independently.

## FreeRTOS reference project

[notwendig/FreeRTOS-eZ80f91](https://github.com/notwendig/FreeRTOS-eZ80f91)
is an independent submodule. Its historical startup reference was
`cc64b750e7a5c6dfd19dd8eb3a644a9243ce10a9`; that is not the current library baseline.

| Dependency | Pinned upstream revision | Compatibility patch |
| --- | --- | --- |
| FreeRTOS-Kernel | V11.3.2, `8a59a4b19bf72977819feddef87d41163ced7004` | `kernel-V11.3.2.patch` |
| FreeRTOS-Plus-TCP | V4.4.2, `b86ad086e9870099bb0ac18a75dcb7f6dd508cc7` | `network-V4.4.2-zds.patch` |
| uzlib | master, `6d60d651a4499a64f2e5b21b4cc08d98cb84b5c1` | `uzlib-6d60d65-zds.patch` |

Patches and setup instructions are in the [subproject build guide](../subprojects/FreeRTOS-eZ80f91/BUILD.md).
The RAM target, matching linker map and original C startup provide the hardware
profile used by the [startup tests](freertos-boot.md).

## CAMELF91_24 and BSP

[notwendig/CAMELF91_24](https://github.com/notwendig/CAMELF91_24) is checked out
at `subprojects/CAMELF91_24`. The polling builder directly reads corrected
commit `af47e6520adc220cef5ee7e9ab96f0c336f7e299`. Historical core analysis
used `b975f3acac08c70c05d951aad22e5c1824446206`; separate workspace core patches
are no longer applied.

The nested public [notwendig/ez80f91bsp](https://github.com/notwendig/ez80f91bsp)
submodule provides the native BSP, currently at `e7742eded429174aa8515bdbdacfa4c169bdc85d`.
See [CAMEL integration](camelf91.md) and [licensing notices](licenses.md).
