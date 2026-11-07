# eZ80F91 development-kit matrix and buttons

```sh
./start.sh --kit
./start.sh --run --kit
./start.sh --kit dbgport 4041
```

`--kit` opens one window with terminal tabs on the left. The compact matrix,
CS2/anode/cathode/modem status, SW1–3, Reset and session status sit in a panel
on the right.
Every terminal has an 80×40 character screen with scrollback and ANSI colors:

| Tab | Connection |
| --- | --- |
| UART0 | Local emulator UART |
| CP/M 2.2 | Local CP/M; shared image/directory drives, direct console/file ports |
| Monitor | Guest UDP 4060; opening the tab sends the initial newline |
| CLI | Guest UDP 4030; local line editing, Enter submits a command |
| Diagnose | Guest TCP 4040 |
| CAMEL24 | Local 24-bit CamelForth; native console/file ports |

CAMEL24 starts when its tab is first opened. Its dictionary, stack and screen
survive tab changes; **Neustart** resets only this Forth instance. Closing the
kit stops that instance. The matrix, buttons and memory panel continue to show
the main kit emulator. [LOAD and SAVE](camelf91-files.md) read and write source
files in the shared Unix tree, for example `3 S" F24ALL.F24" LOAD`.
To open a standalone kit directly on the Forth tab:

```sh
tools/platform.sh kit /tmp/ez80f91-1000/4040.kit.json --port 4040 --camel24
```

The local CAMEL24 and CP/M 2.2 tabs share `cpm-files/A`, `cpm-files/A/1`,
etc., as well as image mounts such as `cpm-files/B.img`. Each drive has one
backend. Select another tree with `--fs-root`. See [CP/M port ABI](cpm-hostfs.md).

The guest field defaults to `ez80<debug-port>` and accepts a hostname or IP
address. A guest terminal connects when first selected. **Trennen** closes
only that connection; **Verbinden** opens it again. Screens and connections
remain available while switching tabs. A disconnected active tab retries
unless explicitly disconnected. Enter `help` in CLI; Enter refreshes Monitor.
CP/M receives Ctrl+C directly. UART Ctrl+C or closing the combined launcher
stops QEMU and saves flash.

ANSI SGR supports normal/bright foreground and background colors, the 256-color
palette, RGB colors, bold/dim, italic, underline and inverse video. Color attributes
are retained per cell, including overwritten text, erased areas and scrollback.
The firmware Monitor fits Ethernet, RTC, heap and button information within
80 columns and 40 rows. Its initial UDP request repeats until output arrives;
returning to the Monitor tab reattaches and redraws the view.

The standalone `kit` command attaches to an existing emulator and provides the
guest terminal tabs without taking over its UART. Closing this standalone
window leaves the emulator running. Without `--run`, the main launcher CPU
waits for ZDS. Build the [Qt 6 platform tools](platform-tools.md)
first. [Forth kit words](camelf91-kit.md)
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
keys 1–3 when the kit board has focus (click the matrix). Terminal keys remain
terminal input. Release, focus loss and window close release all buttons. Inputs are
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

## Memory and speed display

Below SW1–3, the sidebar displays current CS0–3 decoder ranges, internal flash,
SRAM and EMAC RAM, including enabled state. These are live register-derived
windows; internal memory and kit I/O can overlay external windows.
External windows also show their hexadecimal CTL and BMC register values.
The display reflects actual hardware registers, not the ZDS target dialog or
the linker's logical ROM/RAM sections. A fresh debugger-waiting launch shows
the silicon reset map until ZDS initializes the target. For the project's
`eZ80F91_99C0879_RAM` target, initialization configures CS0 at
`100000–1fffff` (CTL `a8`, BMC `00`), CS1 at `000000–07ffff`
(CTL `28`, BMC `00`), CS2 at `800000–bfffff` (CTL `28`, BMC `81`),
internal flash disabled and internal SRAM/EMAC RAM on page `ff`.
The linker places code at `000000–06afff` and data at
`06b000–07ffff,b80000–b8ffff`; calling the code section ROM does not
enable internal flash.

The model clock, measured MIPS and guest/host time ratio come from QEMU's kit
telemetry. Rates update about once per second. The effective model clock is
model MHz multiplied by guest seconds per real second. The eZ80/Z80 MHz values
are explicitly reference estimates using 1/4 clocks per instruction, not a
cycle-accurate conversion of the running workload. Paused and unavailable
instruction-counting states are shown without fabricated MHz estimates.

Rebuild/install both QEMU and the Qt tools, then restart the launcher to enable
these fields. Older telemetry files show that the measurements are unavailable.
