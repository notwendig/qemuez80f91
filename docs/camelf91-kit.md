# CAMELF91 buttons and 5×7 matrix

The words are included in the native ZDS project and the reproducible polling
build. Load a rebuilt Debug image and run the CPU. Use `./start.sh --kit` for
the emulated display. Hardware mapping is documented in [Kit](kit.md).

| Word | Stack effect | Function |
| --- | --- | --- |
| `BUTTON-INIT` | `( -- )` | Configure PB0–2 as inputs, preserving PB3–7. |
| `BUTTONS` | `( -- mask )` | Pressed mask: SW1=1, SW2=2, SW3=4; combines to 0–7; initializes inputs automatically. |
| `BUTTON?` | `( n -- flag )` | Buttons 1=left, 2=center, 3=right; -1 pressed, otherwise 0; invalid numbers return 0. |
| `SW1?` `SW2?` `SW3?` | `( -- flag )` | Direct queries. |
| `MATRIX-INIT` | `( -- )` | Start scanning; repeated calls preserve the image. |
| `MATRIX-CHAR` | `( char -- )` | Display a character, starting scanning automatically. |
| `MATRIX!` | `( addr -- )` | Copy seven consecutive bitmap bytes. |
| `MATRIX-CLEAR` | `( -- )` | Clear the image while scanning continues. |
| `MATRIX-OFF` | `( -- )` | Clear the image and stop Timer1. |

```forth
BUTTONS .
1 BUTTON? .
SW2? .
CHAR A MATRIX-CHAR
CHAR 5 MATRIX-CHAR
MATRIX-CLEAR
MATRIX-OFF
```

ASCII 32–126 is supported. Lowercase uses uppercase glyphs; other cell values,
including negatives and values above 255, display a question mark.

Bitmaps contain seven rows, top to bottom. Bit 4 is the left LED, bit 0 the
right LED, and 1 means on. Bits 5–7 are ignored. The driver copies the source,
so the buffer can be reused.

```forth
CREATE DIAGONAL 16 C, 8 C, 4 C, 2 C, 1 C, 0 C, 31 C,
DIAGONAL MATRIX!
```

Timer1 scans approximately 700 rows/s, or 100 full frames/s. Its ISR preserves
Forth registers, allowing console input and calculations to continue. Rows are
blanked while columns change. The driver owns Timer1 and the kit latches while
active and uses the existing CS2 mapping without reprogramming it. Button reads
are instantaneous, without software debouncing.

The example `examples/camelf91/kit-demo.fth` displays the pressed mask:

```forth
: BTN-DEMO BEGIN BUTTONS 48 + MATRIX-CHAR KEY? UNTIL KEY DROP MATRIX-OFF ;
BTN-DEMO
```

Any UART key exits the loop and turns off the display.

## Sources and tests

`examples/camelf91/kit.inc` is shared with `subprojects/CAMELF91_24/asm/`.
`kit_font.py` generates `kit_font.inc`; the polling builder checks both copies.

```sh
make -C subprojects/CAMELF91_24
python3 tests/test_camelf91_kit.py build/ez80/qemu-system-ez80
python3 tests/test_camelf91_words.py build/ez80/qemu-system-ez80
```

Tests cover all eight masks, release, invalid button numbers, preserved PB3–7,
ASCII/fallback glyphs, bitmap orientation, scanning during calculations,
clear/off and restart after reset. Both guest buffers and integrated display
pixels are compared with expected values.
