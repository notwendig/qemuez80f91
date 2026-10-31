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

## Firmware display driver

The firmware driver owns the animation buffers. `shiftDisplay()` updates only
its working matrix; the timer ISR never reads a shift in progress. Once all
seven rows are shifted, the task publishes the completed image into a pending
buffer. If the previous image is still pending, the producer waits rather than
dropping intermediate scroll positions.

Before row zero, after seven scans, the ISR accepts a pending image. There is
no time-based fallback. The ISR composes a complete seven-row scan snapshot
with a persistent 5×7 overlay. `LED5x7_set(x,y)` sets one overlay bit and
`LED5x7_clr(x,y)` removes it; x=0..4 is left-to-right and y=0..6 top-to-bottom.
Coordinates outside these bounds are ignored. Clearing an overlay bit does not
erase the animation pixel below it. These setters are task-context APIs.
Overlay changes take effect at the next scan boundary, independently of the
animation's seven-scan cadence. The active-low cathode output is the inverse
of the logical animation-OR-overlay image. Rows are blanked before changing
cathodes to avoid electrical row-switch ghosts.

The GUI is passive: QEMU integrates complete hardware scans and publishes only
those images. It does not impose an extra seven-scan delay or a 300-ms partial
frame timer. Static debugger probes before execution remain visible directly.

```sh
python3 tests/test_led_driver.py
python3 tests/test_led_shifts.py build/ez80/qemu-system-ez80
python3 tests/test_kit_frames.py build/ez80/qemu-system-ez80
```

The driver test interrupts working-row updates with real C scan-ISR calls,
checks pending-image backpressure, complete output frames, and set/clear OR
semantics. The shift test assembles the actual eZ80 routine and verifies all
five directions in QEMU, including bounds-safe vertical shifts.

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
