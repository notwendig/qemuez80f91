# Original F91 board startup and PLL

## Tested path

Unmodified `init_params_f91.asm` runs from the reset/TRAP entry in
`vectors24.asm` to the actual FreeRTOS scheduler. The probe also uses original
`cstartup.asm`, `llport.asm` and ZDS `zsldevinitdummy.obj` for peripheral hooks.
It executes interrupt shutdown, CS/bus/internal-memory setup, stack/vector
initialization, clocks and C startup. Test C code initializes UART0/8N1 and two
tasks. Both variants emit `BABABABA!` and halt after seven timer ticks.

The builder takes reviewed startup parameters from
`examples/freertos_tasks/board/probe.json`, originally derived from the native
linker map. A pre-existing IDE-generated map is no longer required. Tests check
memory/PLL registers and the boot stack near B90000h at C entry. They then
alter BSS/DATA and verify original startup restores them after reset, followed
by another full task/stack/tick check.

| Variant | Oscillator | Startup source | Final system clock |
| --- | ---: | --- | ---: |
| `board` | 50 MHz | Oscillator, original parameters | 50 MHz |
| `pll` | 10 MHz | PLL, multiplier 5 | 50 MHz |

The original `_SYS_CLK_SRC=0` disables PLL selection. The PLL variant changes
only linked `_OSC_FREQ`, `_SYS_CLK_SRC` and `_OSC_FREQ_MULT` values.

## Clock model

The F91 clock device provides PLL_DIV_L/H and PLL_CTL0/1 at 5Ch–5Fh and supplies
Timer0's clock.

- Reset selects the oscillator, normally 50 MHz, with PLL off.
- `osc-frequency` accepts 1–50000000 Hz; use 10000000 for the PLL probe.
- The 11-bit divider latches low on write and commits on high write; values
  below two become two. Reads return zero.
- Divider/charge-pump/lock settings are writable only with PLL off; reserved bits read zero.
- Functional lock delay is 100 µs of guest time. Inputs of 1–10 MHz and outputs
  up to 50 MHz are accepted. This is a modeling choice, not measured analog timing.
- An off/unlocked PLL cannot be selected; a selected PLL cannot be disabled.
  Reserved MUX selection 3 preserves the old source.
- Lock/unlock events latch until PLL_CTL1 is read; enables control IRQ source
  3, vector 04Ch.
- RTC clock selection supplies an ideal 32768-Hz source. The separate
  [RTC calendar device](rtc.md) is also implemented.
- Timer0 preserves its remaining count and reschedules it when the source changes.

Charge pump, jitter, analog lock sensitivity, exact CPU cycles and UART transmit
baud timing are not modeled. Timer rounding uses whole ticks/nanoseconds;
CPU time follows QEMU icount. Hardware references: PS019217-1222 pp. 25–26,
57–58 and 265–273, particularly tables 152–155. BIT/RES/SET and indexed CB
operations are covered by the CPU regressions and [CAMEL tests](camelf91.md).

## Scope and limits

This probe runs with `ram-boot=on`, external SRAM and internal flash disabled.
It does not test cold-flash boot or the full application. Executing shutdown
writes for I2C, SPI, UART1, Timer2/3 or GPIO without device models does not
establish those devices' behavior. EMAC, RTC and Timer1 now have separate models
and tests; see [Status](status.md). Vendor peripheral hooks remain dummies here.

## Saved images and tests

`examples/freertos_tasks/board/` contains `probe.bin/json/map` for the oscillator
variant and `pll.bin/json/map` for PLL. Current raw images are **444901 bytes**
each; ROM allocation is 13650 bytes. The reference linker profile uses ROM
000000h–06AFFFh, application RAM 06B000h–07FFFFh, CP/M RAM B80000h–B8FFFFh
and stack B90000h.

```sh
build/ez80/qemu-system-ez80 -M ez80f91-freertos,ram-boot=on,osc-frequency=10000000 -kernel examples/freertos_tasks/board/pll.bin -icount shift=0 -display none -monitor none -serial mon:stdio
python3 tests/test_board_startup.py build/ez80/qemu-system-ez80
python3 tests/test_pll.py build/ez80/qemu-system-ez80
```

The board test runs both variants before and after reset; a second argument
selects one image. **Ctrl+A, X** exits an interactive halted instance.
The PLL test checks reset values, write protection, divider latching/minimum,
lock events, cancellation, invalid inputs, all three clock sources and competing
PLL/Timer0 IRQ priorities, including reset repeats.

## Rebuild

```sh
python3 examples/freertos_tasks/build.py --scenario board --zds /path/to/ZDSII_eZ80Acclaim!_5.3.5 --freertos /path/to/FreeRTOS-eZ80f91 --kernel /path/to/FreeRTOS-Kernel --out build/freertos-board
python3 examples/freertos_tasks/build.py --scenario pll --zds /path/to/ZDSII_eZ80Acclaim!_5.3.5 --freertos /path/to/FreeRTOS-eZ80f91 --kernel /path/to/FreeRTOS-Kernel --out build/freertos-pll
```

The kernel baseline is V11.3.2 with the project patch. `preempt`, `blocking`
and `wrap` remain available. Metadata includes the startup-source hash and all
reviewed parameters. Both board variants were rebuilt and tested with V11.3.2.
Earlier milestone-wide test counts are historical, not a claim of a new full run.
