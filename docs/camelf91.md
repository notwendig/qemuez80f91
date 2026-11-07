# CamelForth for eZ80F91

`subprojects/CAMELF91_24` is an independent Git submodule containing 24-bit
CamelForth, native ZDS board startup and development-kit words. The polling
builder uses corrected commit `af47e6520adc220cef5ee7e9ab96f0c336f7e299` directly.
The earlier `b975f3a` baseline is retained only as a historical reference.

## Two build paths

| Path | Console and output | Purpose |
| --- | --- | --- |
| Native ZDS project | Interrupt-driven UART0 through `libbsp`; `Debug/camel_f91.lod`/`.hex` | Board and source debugging |
| Kit native-port build | `examples/camelf91/camel-hostfs.bin`; direct console/file I/O | Shared [Unix CP/M filesystem](cpm-hostfs.md) |
| Workspace polling build | Polling adapter; `build/camelf91/camel.bin`/`.json`/`.map` | Reproducible regression tests and a separate ZDS project |

The [dictionary test](camelf91-words.md) executes 237 entries and makes 201
result checks. A separate UART regression runs 89 cases before and after reset.
[Kit words](camelf91-kit.md) cover buttons and the matrix.

## Native setup and build

```sh
sh scripts/setup-camelf91.sh
```

Setup initializes CAMEL and its nested public `ez80f91bsp` dependency.
It no longer requires the former local SSH configuration or unavailable BSP revision.

1. Build `libbsp/libbsp.zdsproj` with ZDS II 5.3.5, **Debug → Rebuild All**.
2. Open `camel_f91.zdsproj` and rebuild **Debug**.
3. Select the RAM target and Ethernet Smart Cable or the appropriate hardware
   debugger. Load `Debug/camel_f91.lod`, then press **F5**.

After ZDS has generated its makefile, Linux/Wine can also build with:

```sh
make -C subprojects/CAMELF91_24
```

`ZDS_HOME`, `WINE` and `BUILD` are configurable. Native `_main` calls
`init_uart0` after `init_bsp`, selecting 115200 baud, 8N1. The BSP's board-pin
initialization alone does not initialize the console. The RAM debug target
uses `externalAutoSelect=false`, since CS0 external flash is disabled there.

## Reproducible polling build

```sh
python3 examples/camelf91/build.py --zds "$ZDS_HOME"
tools/platform.sh f24 --prepare-only
```

The builder reads the pinned corrected assembly sources, enables the shared
kit includes and delegates UART setup to the polling BSP. It rejects unreviewed
local assembly changes. IDE settings do not alter this image.

`console.inc` declares the console ABI; `poll_bsp.asm` initializes UART0 and
provides `init_bsp`, `putc`, `getc` and `kbhit` without UART interrupts.
`__cstartup=1` enables original BSS/DATA initialization. Native and workspace
`kit.inc`/`kit_font.inc` files must match.

Metadata records the source commit, source hashes, symbols and binary SHA-256.
No CAMEL patch hash is required. The saved image is 10688 bytes, with 441 bytes
of static RAM plus Forth stacks/work areas. The map lists 10691 ROM bytes,
including three reserved bytes omitted from the raw image.

## Tested memory and clock profile

| Range | Use |
| --- | --- |
| 000000h–07FFFFh | External SRAM used for code |
| B7D000h–BFFFFFh | Linker RAM, internal RAM and upper external SRAM |
| C00000h | Initial stack top; the first push is below it |
| 800000h–800002h | Kit latches with kit enabled and matching CS2 |
| System clock | 50-MHz oscillator, PLL disabled |

Release/Chiponly have separate linker/target settings. These tests cover Debug RAM.

## Use and tests

```sh
tools/platform.sh f24
python3 tests/test_camelf91.py "$QEMU_EZ80"
python3 tests/test_camelf91_words.py "$QEMU_EZ80"
python3 tests/test_camelf91_kit.py "$QEMU_EZ80"
```

```forth
1 2 + .
: SQUARE DUP * ;
12 SQUARE .
BUTTONS .
CHAR A MATRIX-CHAR
MATRIX-OFF
```

The launcher creates `build/f24/`. See [ZDS operation](start-f24.md) and
[core analysis](camelf91-analysis.md) for commands and corrected defects.
Original port and usage notices remain in the subproject's `ReadMe.txt`,
`LICENSE` and source headers; see [Licenses](licenses.md).

## FreeRTOS project integration

`subprojects/FreeRTOS-eZ80f91/EZ80F910300ZCOG.zdsproj` also builds the four
CAMEL24 assembler modules from the sibling `CAMELF91_24/asm` directory.
Both Debug and Release define `CAMEL_FREERTOS` and `FLASH_BOOT`, using the
same Flash target and ROM/RAM ranges. Debug retains its source symbols. The FreeRTOS C startup remains
the firmware entry; CAMEL24 starts as a statically allocated task at priority 2.

Built-in dictionary headers, primitives and high-level words live in ROM/flash.
The initial user-area template is also in ROM; its mutable copy is in BSS.
The reserved bank `B80000–B8FFFF` contains the RAM dictionary, Forth task stack,
return/leave stacks, PAD and HOLD. New colon definitions and variables start
at `B80000`; the 3072-byte task stack starts at `B8E000` and is the same stack
registered with the FreeRTOS TCB. The kernel heap does not own this bank.

`camel_console.asm` uses the ports from `CPM/CPM22/HWC.INC`: input/output on
8Ch/8Dh. Waiting for input calls `vTaskDelay(1)` while preserving interpreter
registers. `bye` deletes only the Forth task. The existing standalone Kit ROM
continues to use its own polling BSP; `examples/camelf91/freertos-core.patch`
records the reviewed conditional core changes used by both builds. The setup
scripts apply it automatically; repeated setup recognizes an applied patch.

To exercise the linked task in an isolated emulator with a native console:

```sh
python3 tests/test_freertos_camel.py build/ez80/qemu-system-ez80 \
  subprojects/FreeRTOS-eZ80f91/Release/EZ80F910300ZCOG.hex
```

The test checks ROM built-ins, a newly compiled RAM definition, scheduler
progress while Forth waits for input, 194 core word checks and numeric-drive SAVE. The standalone Kit peripheral
words are excluded here because the FreeRTOS LED driver owns Timer1.
It attaches a QEMU console device directly; the Kit's existing standalone
CAMEL24 tab remains a separate interpreter session.
