# eZ80F91 development-kit matrix and buttons

```sh
./start.sh --kit
./start.sh --run --kit
./start.sh --kit dbgport 4041
```

`--kit` opens the matrix/button window beside UART. Without `--run`, the CPU
waits for ZDS. Closing the kit window closes only the display; exiting the UART
launcher also closes the kit. Python/Tkinter is required. [Forth kit words](camelf91-kit.md)
include `BUTTONS .` and `CHAR A MATRIX-CHAR`.

Mapping follows UM014220-0508 tables 8, 9 and 15 and the Zilog QuickStart LED
orientation: seven rows by five columns.

| Address | Function |
| --- | --- |
| 800000h | Active-high anode bits 0–6; bit 7 selects GPIO input |
| 800001h | Active-low cathodes 0–4; bits 5/6/7 are modem reset/Trig1/Trig2 |
| 800002h | GPIO latch; unconnected input reads FFh |

Anode bit 0 is the top row, bit 6 the bottom. Cathode bit 4 is left, bit 0 right.
Anode/cathode registers are write-only and read FFh; the GPIO latch is readable
and writable. Reset leaves the display dark.

Kit registers appear only when enabled and CS2 covers 800000h. Higher-priority
CS0/1 and internal memory still take precedence. Without kit state enabled,
these addresses retain their ordinary memory mapping.

## Complete-scan display

QEMU integrates each LED's on-time across all seven rows, filtering brief
switching pulses. Publication occurs only after the last row's on-time ends.
The previous complete frame remains visible during slow or paused scans.
Pixels redraw only when the complete mask changes; registers/buttons update
independently. Every complete scan is accepted, including continuously moving
text. Requiring duplicate frames previously stalled scrolling.

Static dark/parallel output is accepted after 40 ms without an anode change.
Debugger writes before the first CPU start remain immediately visible.
This is not an electrical current/brightness/GAL timing simulation. Optional
modem LEDs D1–4 have no modem model; displayed modem/trigger values are latch bits.

State is `/tmp/ez80f91-<uid>/<port>.kit.json`. A direct launch can set
`-global ez80f91-memory.kit-led-state=/tmp/kit.json`. The launcher manages the
window and state file with its instance.

```sh
python3 tests/test_kit.py build/ez80/qemu-system-ez80
python3 tests/test_kit_frames.py build/ez80/qemu-system-ez80
```

Tests check polarity/orientation, GPIO direction, CS enable/priority, reset and
actual seven-row multiplex code. Frame tests pause after each row, including
more than 40 ms guest time per row, and reject partial images. They cover new
glyphs, all-dark frames and per-scan scrolling changes using FreeRTOS masks;
the Forth driver is not modified for these tests.

## Buttons

SW1/2/3 (left/center/right) connect to PB0/1/2. Hold the mouse button or keyboard
keys 1–3. Release, focus loss and window close release all buttons. Inputs are
active low. SW4 requests system reset.

The window uses the adjacent `<port>.qmp` Unix socket; `--qmp` selects another.
The memory device's `kit-buttons` property contains pressed mask 0–7.
PB_DR/DDR/ALT1/ALT2 are at 9Ah–9Dh; dual-edge IRQ vectors are A0h/A4h/A8h.
Write ones to PB_ALT0 (A7h) to acknowledge. Other GPIO IRQ modes are not modeled.

```sh
python3 tests/test_kit_buttons.py build/ez80/qemu-system-ez80
```

The button test uses the same QMP controls as the window and checks input,
press/release IRQs, acknowledgment and reset with real guest handlers.
