# Test catalog

The native C++/Qt tools additionally use Qt Test and a QEMU launcher check:

```sh
ctest --test-dir build/platform-tools --output-on-failure
python3 tests/test_platform_launch.py
```

Tests are standalone Python scripts using QMP/GDB, UART and small guest programs.
Run them directly, not through pytest. Set `QEMU_EZ80` to the current executable.
Local Unix/TCP sockets must be allowed; most tests need no network bridge.
The shared VM helper uses a fresh temporary working directory by default, so
ordinary tests neither load nor overwrite saved workspace flash. Persistence
tests explicitly select their own temporary directory.

## Local emulator and fixture tests

```sh
export QEMU_EZ80="$PWD/build/ez80/qemu-system-ez80"
python3 tests/test_smoke.py "$QEMU_EZ80"
python3 tests/test_cpu_uart.py "$QEMU_EZ80"
python3 tests/test_memory.py "$QEMU_EZ80"
python3 tests/test_camelf91.py "$QEMU_EZ80"
```

| Group | Scripts |
| --- | --- |
| CPU/decoder | `test_smoke.py`, `test_cpu_uart.py`, `test_cstartup_ops.py`, `test_extended_opcodes.py`, `test_opcode_maps.py`, `test_illegal_traps.py` |
| Memory/flash | `test_memory.py`, `test_chip_selects.py`, `test_flash_uart.py`, `test_internal_flash.py`, `test_flash_persistence.py` |
| Clock/timer/RTC | `test_timer_irq.py`, `test_pll.py`, `test_rtc.py` |
| MAC/debugger | `test_emac.py`, `test_dbgport.py` |
| Saved ZDS/RTOS images | `test_zds_cstartup.py`, `test_freertos_vectors.py`, `test_freertos_tasks.py`, `test_freertos_blocking.py`, `test_board_startup.py` |
| Kit | `test_kit.py`, `test_kit_frames.py`, `test_kit_buttons.py` |
| Forth | `test_camelf91.py`, `test_camelf91_words.py`, `test_camelf91_kit.py` |

Runtime tests take QEMU as their first argument. Opcode-map checks additionally
use local QEMU sources and a host C compiler; they can run without a QEMU
argument. Saved-image tests verify metadata/hashes rather than rebuilding firmware.

## Complete Forth and kit coverage

```sh
make -C subprojects/CAMELF91_24
python3 tests/test_camelf91_words.py "$QEMU_EZ80"
python3 tests/test_camelf91_kit.py "$QEMU_EZ80"
python3 tests/test_kit_frames.py "$QEMU_EZ80"
```

The first two scripts use native Debug HEX and its matching map by default;
`--hex`/`--map` select alternatives. The dictionary runner records entry coverage
and fails on missing words. See [Dictionary tests](camelf91-words.md).
The frame test pauses after every row and changes each complete scan, checking
both retained partial-scan display and continuously progressing scrolling text.
See [Kit behavior](kit.md).

## Host CP/M decompression

After FreeRTOS/uzlib setup:

```sh
python3 tests/test_freertos_unzip.py
```

This compiles the actual wrapper and uzlib with the host compiler. It tests the
original 256256-byte disk, callbacks, CRC, truncation and output bounds. It needs
neither QEMU nor a running guest.

## Original ZDS/Nexus DLL

With vendor SDK, Wine and MinGW installed:

```sh
python3 tests/test_zds_ethernet.py --qemu "$QEMU_EZ80" \
  --zds "$ZDS_HOME" --sdk /path/NexusSDK_1.1 --native --sdk-scan
python3 tests/test_zds_flash.py --qemu "$QEMU_EZ80" \
  --zds "$ZDS_HOME" --sdk /path/NexusSDK_1.1
```

These tests use isolated instances, available local ports and temporary flash
files. SDK/Windows-DLL requirements distinguish them from ordinary local tests.

To exercise a ROM larger than internal flash with the original ZDS IDE:

```sh
python3 tests/test_zds_flash_boundary.py --qemu "$QEMU_EZ80" --zds "$ZDS_HOME"
```

This builds and downloads a 260-KiB ROM through the Ethernet Smart Cable DLL,
compares every byte through `0x040FFF`, reads data across `0x03FFFF–0x040000`,
and calls external code at `0x040020`. A second emulator instance verifies cold
boot from the saved flash files. Artifacts and logs stay in
`build/zds-flash-boundary`; the live debugger and firmware are unaffected.
The IDE can still report its external-flash selection warning; successful loading,
readback and execution are checked independently.

## CP/M image/directory drives and 8-bit I/O

```sh
python3 tests/test_cpm_hostfs.py "$QEMU_EZ80"
python3 tests/test_cpm_hostfs_cli.py "$QEMU_EZ80"
python3 tests/test_wd2797a.py "$QEMU_EZ80" --8bit
```

These tests mix private directory drives and CP/M image files. They verify the
FCB port ABI, 256 high-address mirrors, user areas, sequential/random files,
protections, and actual BIOS/BDOS execution of DIR, TYPE, PIP, REN, ERA and SDIR.
The CLI test executes COM programs calling BIOS READ/WRITE over the 8-bit FDC,
checking that FCB and raw sector writes are mutually visible. Image contents
are independently checked with cpmtools, including extent boundaries and disk-full
protection. Qt tests load all 198 Forth checks from both a directory and an image.

## Running firmware and real networking

```sh
python3 tests/test_freertos_buttons.py /tmp/ez80f91-1000/4040.qmp
tools/platform.sh demo --test
```

These are manual integration tests. Matching firmware, QMP/IP addresses and the
current FreeRTOS linker map are required. CP/M runs in the single local Kit
tab through direct ports; the retired firmware TCP 4050 test is not applicable.
The ZTP demo expects nadibox DHCP and real host UDP/TCP peers.
Do not run these indiscriminately through a `test_*.py` glob.

For the UDP SysInfo monitor on port 4060, test repeated attachment with:

```sh
python3 tests/test_freertos_monitor.py ez804040 4060
```

The test opens three different source ports in sequence, checks each new
viewer's banner and updates, and verifies that old endpoints stop receiving.
It temporarily selects its own monitor endpoints; reconnect netcat and press
Enter afterwards to resume viewing there.

## Updated full FreeRTOS application

The project uses kernel V11.3.2, Plus-TCP V4.4.2 and uzlib `6d60d65`.
Build the full board image first and convert HEX with `scripts/ihex_to_bin.py`.
For the locally generated validation image:

```sh
python3 tests/test_freertos_network.py build/ez80/qemu-system-ez80 build/freertos11-full/freertos11.bin
python3 tests/test_freertos_network.py build/ez80/qemu-system-ez80 build/freertos11-full/freertos11.bin --hostname Labor-4040
python3 tests/test_freertos_network.py build/ez80/qemu-system-ez80 build/freertos11-full/freertos11.bin --cli
python3 tests/test_freertos_network.py build/ez80/qemu-system-ez80 build/freertos11-full/freertos11.bin --cli --monitor
python3 tests/test_hostname.py build/ez80/qemu-system-ez80
```

The isolated Ethernet-socket test supplies DHCP Offer/Ack, answers ARP, checks
ICMP Echo and establishes TCP port 4040. Actual Uptime console data must arrive.
With `--cli`, it also exercises UDP 4030: help, IP configuration, fragmented
input, RTC date/time, memory/Intel HEX output, invalid commands/parameters,
oversized-line recovery and a new client source port.
`--monitor` captures real UDP 4060 output, verifies cursor positions and field
widths against an 80×40 screen, and writes `build/freertos-cli/monitor.ansi` for
rendering in the Qt terminal.
It also checks full 32-bit DHCP/ARP diagnostic addresses, rejecting the former
`255.168.77.*` truncation. It requires no bridge or external DHCP server.
Use freshly rebuilt firmware: DHCP DISCOVER and REQUEST must include option 12
with `ez800` (no debug port) or the name passed through `--hostname`. The board
configuration test checks CLI defaults/validation/forwarding, actual CPU I/O,
the selected debug port, read-only data, 63-byte names and guest reset.

## Reports and interpretation

[Validation](validation.md) records dated executed checks. Reports/logs reside
under `build/` or temporary test directories. Success establishes the specified
scenario, not exhaustive instructions, register combinations or hardware timing.
Board/PLL fixtures rebuild without a pre-generated IDE map; reviewed startup
parameters come from `examples/freertos_tasks/board/probe.json`.

Kit memory, clock and performance telemetry:

```sh
python3 tests/test_kit_statistics.py build/ez80/qemu-system-ez80
```

This uses an isolated instruction loop to check decoder ranges, the selected
clock, instruction/virtual/host counters and paused state. Qt tests also verify
the displayed MIPS, derived MHz and reference estimates.


## VSCodium / IDE-free firmware workflow

```sh
python3 tools/firmware.py build --config Release
python3 tests/test_firmware_flash.py build/ez80/qemu-system-ez80 build/firmware/Release/build.json
python3 tests/test_freertos_camel.py build/ez80/qemu-system-ez80 build/firmware/Release/EZ80F910300ZCOG.hex
```

The flash test uses a temporary working directory. It checks SHA/CRC validation,
backups, rollback after a second-image write failure, refusal to replace live
QEMU flash, a clean QMP shutdown and cold boot from the persistent files alone.
It does not touch the developer's running Kit or flash images. See
[VSCodium tasks](vscodium.md) for build/deploy commands.
