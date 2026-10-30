# eZ80 core and eZ80F91 implementation baseline

## References and scope

Local vendor references are `../doc/um0077.pdf` (UM007715-0415) and
`../doc/ps0192.pdf` (PS019217-1222). Page numbers below are printed pages;
PDF positions are nine pages higher in these revisions. The target is the
F91 MCU from PS0192, not the F91 ASSP described by PS0270.

The eZ80 is a CPU core; eZ80F91 is a specific MCU containing it. F91 is not a CPU
mode, and an ordinary Z80 interpreter is insufficient.

| Area | CPU core | F91 SoC / virtual board |
| --- | --- | --- |
| Execution | Registers, ALU, decoder, flags, prefixes | Variant and clock settings |
| Addressing | Z80/ADL, MBASE, SPS/SPL | Decoding and remapping |
| Interrupts | Acceptance, frames, mode changes, return | Sources, priorities and vectors |
| Memory | Memory and I/O access instructions | Flash, RAM, chip selects, wait states |
| Devices | No UART registers in the decoder | UART, GPIO, timers, EMAC and other devices |

UM0077 pp. 6–18 defines modes and registers. Reset enters Z80 mode; MBASE is
the upper byte of short addresses. ADL permits 24-bit addresses/registers.
SPS/SPL and .SIS/.SIL/.LIS/.LIL require explicit modeling. `.ASSUME ADL=1`
is an assembler directive, not a hardware mode switch.

PS0192 p.39 specifies a 16-bit interrupt state and `LD I,HL` (ED C7) /
`LD HL,I` (ED D7). UM0077 pp.195/200 excludes these from certain other eZ80
variants. The F91 therefore requires a 16-bit I register rather than blindly
copying another variant. LD HL,I is now implemented using its detailed flag
description; the conflicting summary remains documented in
[Extended instructions](extended-opcodes.md).

## Reset and memory

PS0192 p.41 sets reset PC to zero and GPIO to inputs. Hardware reset sources
include power-on, brownout, RESET pin, configured watchdog, RTC sleep wakeup and
debug reset. The hardware controller's 1025-SCLK sequence is not electrically
or cycle-accurately modeled. Do not assume all other registers reset to zero.

| Resource | Reset mapping/value | PS0192 reference |
| --- | --- | --- |
| Program flash, 256 KiB | 000000h–03FFFFh, enabled | pp.104–105, tables 37–38 |
| General RAM, 8 KiB | FFE000h–FFFFFFh, enabled | pp.94–95, tables 32–33 |
| EMAC RAM, 8 KiB | FFC000h–FFDFFFh, enabled | pp.94–95, tables 32–33 |
| RAM_CTL, B4h | C0h | table 32 |
| RAM_ADDR_U, B5h | FFh | table 33 |
| FLASH_ADDR_U, F7h | 00h, bits 1:0 reserved | table 37 |
| FLASH_CTRL, F8h | 88h, enabled with four wait states | table 38 |

RAM_ADDR_U relocates EMAC RAM at offset C000h and general RAM at E000h.
Flash relocates on 256-KiB boundaries. Priority is internal RAM, internal flash,
then external chip selects. Current [memory](chip-selects.md) and
[flash](flash-uart.md) models extend the initial baseline.

## UART0 baseline

These are I/O addresses, not memory addresses. References: PS0192 pp.35–36,
182–194, particularly tables 102/106.

| Port | Register | Reset/meaning |
| --- | --- | --- |
| C0h | RBR read / THR write | Receive/transmit with DLAB=0 |
| C0h | BRG_L | 02h with DLAB=1 |
| C1h | IER / BRG_H | 00h, selected by DLAB |
| C2h | IIR read / FCTL write | 01h / 00h |
| C3h | LCTL | 00h; bit 7 is DLAB |
| C4h | MCTL | 00h |
| C5h | LSR | 60h; THRE bit 5, TEMT bit 6 |
| C6h | MSR | Unspecified reset value (XX) |
| C7h | SPR | 00h |

DLAB redirects C0/C1 to baud divisors; divisor writes must not emit characters.
LCTL=03h selects 8N1. Pin multiplexing and clocks gate UART access.
FIFO, interrupts and loopback have since been added; [Flash/UART](flash-uart.md)
is the current behavior reference.

## Initial acceptance milestone

The first milestone pinned QEMU/tooling, implemented minimum Z80/ADL execution,
reset memory and UART, and ran a ROM that enabled ADL, set SPL, initialized UART,
polled LSR and printed `Hello eZ80F91`.

Acceptance required repeatable builds, exact output, tested mode transition,
DLAB switching and explicit diagnostics for unsupported behavior. Independent
CPU tests checked width boundaries and stacks. A successful UART demonstration
alone never established complete F91 compatibility.
