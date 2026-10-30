# Test catalog

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

## Running firmware and real networking

```sh
python3 tests/test_freertos_buttons.py /tmp/ez80f91-1000/4040.qmp
python3 tests/test_freertos_cpm.py 192.168.77.26
python3 -m tools.demo --test
```

These are manual integration tests. Matching firmware, QMP/IP addresses and the
current FreeRTOS linker map are required. First CP/M decompression may take
minutes. The ZTP demo expects nadibox DHCP and real host UDP/TCP peers.
Do not run these indiscriminately through a `test_*.py` glob.

## Updated full FreeRTOS application

The project uses kernel V11.3.2, Plus-TCP V4.4.2 and uzlib `6d60d65`.
Build the full board image first and convert HEX with `scripts/ihex_to_bin.py`.
For the locally generated validation image:

```sh
python3 tests/test_freertos_network.py build/ez80/qemu-system-ez80 build/freertos11-full/freertos11.bin
```

The isolated Ethernet-socket test supplies DHCP Offer/Ack, answers ARP, checks
ICMP Echo and establishes TCP port 4040. Actual Uptime console data must arrive.
It also checks full 32-bit DHCP/ARP diagnostic addresses, rejecting the former
`255.168.77.*` truncation. It requires no bridge or external DHCP server.

## Reports and interpretation

[Validation](validation.md) records dated executed checks. Reports/logs reside
under `build/` or temporary test directories. Success establishes the specified
scenario, not exhaustive instructions, register combinations or hardware timing.
Board/PLL fixtures rebuild without a pre-generated IDE map; reviewed startup
parameters come from `examples/freertos_tasks/board/probe.json`.
