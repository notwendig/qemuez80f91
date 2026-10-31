# Documentation

Maintained guides and project READMEs use English. Commands, register names,
API names and ZDS menu labels retain their original spelling. Original vendor
manuals, source notices and license documents remain authoritative.

## Getting started and operation

| Guide | Contents |
| --- | --- |
| [Getting started](getting-started.md) | Dependencies, checkout, build, installation and first ROM |
| [Status](status.md) | Current capabilities, tested scope and limitations |
| [Architecture](architecture.md) | CPU, devices, memory, time model and debugging |
| [Development](development.md) | Repositories, patches, generated files and publication |
| [Testing](testing.md) | Local, SDK-dependent and live-firmware tests |
| [Sources](sources.md) | Manuals and pinned dependency versions |
| [Licenses](licenses.md) | Origins and existing licensing notices |

## Firmware

| Project | Guides |
| --- | --- |
| CamelForth | [Integration](camelf91.md), [ZDS launch](start-f24.md), [Core fixes](camelf91-analysis.md), [Dictionary test](camelf91-words.md), [Buttons and matrix](camelf91-kit.md) |
| FreeRTOS | [Project README](../subprojects/FreeRTOS-eZ80f91/readme.md), [Build](../subprojects/FreeRTOS-eZ80f91/BUILD.md), [C startup](freertos-boot.md), [Tasks](freertos-tasks.md), [Blocking and rollover](freertos-blocking.md), [Board startup](board-startup.md) |
| BSP | [Library and interfaces](../subprojects/CAMELF91_24/libbsp/README.md) |
| ZTP | [Original TCP/UDP demonstration](ztp-tcpudp.md) |

## Devices and debugging

- [All on-chip devices and register inventory](onchip.md)
- [Memory and chip selects](chip-selects.md)
- [Flash and UART](flash-uart.md)
- [Timers, interrupts and vectors](timer0-interrupts.md)
- [RTC](rtc.md)
- [Ethernet MAC and PHY](emac.md)
- [Kit display and buttons](kit.md)
- [Ethernet Smart Cable / ZDS II](zds-ethernet.md)
- [Extended instructions](extended-opcodes.md)

## Implementation references

[QEMU base](qemu-base.md) identifies the required upstream revision.
[F91 baseline](ez80f91-baseline.md) records hardware references and reset values.
[First execution](first-execution.md) describes a historical CPU/UART milestone;
its original limitations are not the current feature list.
[Validation](validation.md) separates historical release checks from subsequent upgrades.
