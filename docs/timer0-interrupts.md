# Timer0, Timer1 and the F91 vector path

## Original vector probe

The unmodified project `EZ80F910300ZCOG/src/vectors24.asm` is exercised from
reset/TRAP through `__init_default_vectors` and `_set_vector`. Historical
reference commit: `cc64b750e7a5c6dfd19dd8eb3a644a9243ce10a9`; source SHA-256:
`994be83e3f99fe062e8c05de8089f1badcc43e6112527d1dbc9e39a40f943b2b`.

Timer0 enters the generated trampoline and original `irq` register wrapper.
A test handler reads TMR0_IIR, increments a counter and emits `T`; after three
ticks, main stops the timer and halts. Expected output is `TTT`, with prepared
BC/DE/HL/IX/IY/SPL preserved. Reset repeats the sequence.

Test hooks and an unused `switch` stub allow linking without the kernel.
Actual switching is tested in [FreeRTOS tasks](freertos-tasks.md); full startup
is tested in [Board/PLL](board-startup.md).

## Interrupt and timer implementation

- A 48-input controller provides two priorities, INT_P0–5 at 10h–15h and fixed
  ordering within each level. Unused sources 9/10 are masked. Timer0 is source
  5/vector 054h; Timer1 source 6/vector 058h; PLL source 3/vector 04Ch.
  [EMAC](emac.md), [flash/UART](flash-uart.md) and [buttons](kit.md) supply additional IRQs.
- ADL vector base is `(I & FFFE) << 8`; Z80 without MADL uses MBASE plus
  `(I & FE) << 8`. The 9-bit vector replaces the low I bit.
- Entry clears IEF1/IEF2. EI allows acceptance only after the following instruction.
  An acceptable IRQ wakes HALT.
- Without MADL, return addresses use SPS or SPL. With MADL, entry switches to
  ADL/SPL and stores F91 marker 0/1. RETI.L restores mode and PC; CALL/RET markers
  2/3 are separate. RETI does not set IEF itself; the ISR executes EI.
- Timer0 registers are 60h–64h; Timer1 65h–69h. Both support single/continuous
  operation, reload, divisors 4/16/64/256, EOC, interrupt enables and read-to-clear IIR.
- Reading data-low latches high. RR writes update reload; RLD loads the counter.
  Reload zero means 65536 counts.
- CLK_PPD2 (DCh) bits 0/1 independently freeze Timer0/1, preserving remaining counts.
  Timer2/3 are not implemented.
- The [clock device](board-startup.md) supplies oscillator/PLL/RTC sources.
  At 50 MHz, reload 3125/divisor 16 gives 1 ms. Missed periods coalesce into
  one EOC bit rather than forming an artificial IRQ queue.

References: PS019217-1222 pp. 48, 57–62, 123–138; UM007715-0415 pp. 36, 297–299.
F91 markers override generic CPU descriptions. RETN is implemented, but NMI sources
remain absent. IM is stored; F91 maskable interrupts use the vector path.
External timer/RTC sources, electrical outputs, BRK_STOP and exact instruction
cycles are not modeled. Global QEMU pause freezes virtual time.

## Run and rebuild

```sh
build/ez80/qemu-system-ez80 -M ez80f91-freertos,ram-boot=on -kernel examples/timer0_vectors/probe.bin -icount shift=0 -display none -monitor none -serial mon:stdio
```

Expect `TTT`, then HALT; **Ctrl+A, X** exits. The saved file is 438529 bytes
because initialized RAM at 06B100h leaves an FF-filled gap. Actual code uses
1876 bytes according to its map.

```sh
python3 examples/timer0_vectors/build.py --zds /path/to/ZDSII_eZ80Acclaim!_5.3.5 --freertos /path/to/FreeRTOS-eZ80f91 --out build/timer0-vectors
python3 tests/test_freertos_vectors.py build/ez80/qemu-system-ez80 build/timer0-vectors/probe.bin
python3 tests/test_timer_irq.py build/ez80/qemu-system-ez80
```

Sources, image, map and metadata are in `examples/timer0_vectors/`. Rebuilding
copies the original vector source unchanged from the specified project.

Tests cover periodic 1-kHz IRQs, HALT wakeup, RETI/RETI.L, Z80-to-ADL entry and
marker 0, odd-I masking/512-byte vector alignment, EI delay, single-pass disable,
EOC clearing, high-byte latches, clock freeze/resume and original register wrappers.
PLL/Timer0 arbitration is tested with reversed priorities. Additional block-I/O
and SLP cases are in [Extended instructions](extended-opcodes.md).

## FreeRTOS display and monitor

`LED5x7Tick` uses Timer1/vector 058h; without it the display tasks stall waiting
for scans. Timer1 shares the system source but has independent counter/reload/IRQ
state. `test_timer_irq.py` checks both sources and independent gating.

```sh
nc -u 192.168.77.26 4060
```

The first UDP datagram (for example Enter in netcat) starts the ANSI SysInfo
monitor. `./start.sh --kit` opens the matrix. The display publishes complete
scans and retains the last complete frame between updates, even when execution
is slower than real time; see [Kit](kit.md).
