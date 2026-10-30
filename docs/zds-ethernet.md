# ZDS II over Ethernet Smart Cable / ZDI

QEMU communicates with the installed, unmodified `nxEz80EthernetSC.dll`.
References are Nexus SDK 1.1, installed `config/eZ80F91algo.ini` and integration
tests running the actual PE32 DLL under Wine.

## Start and connect

For CAMEL source debugging, use `python3 tools/zds/f24.py` as described in
[CAMEL launch](start-f24.md). For a direct launch after [building QEMU](getting-started.md):

```sh
build/ez80/qemu-system-ez80 \
  -M ez80f91-freertos,ram-boot=on -kernel examples/camelf91/camel.bin \
  --dbgport=4040 --scan-dev -S -display none -monitor none -serial stdio -nic none
```

`--dbgport=4040` starts TCP debugging and automatically enables Scan Device on
UDP 3000; explicit `--scan-dev` is optional. `-S` pauses until debugger Run.
The service binds all IPv4 interfaces. Use `127.0.0.1` locally or the host's
LAN address (192.168.77.3 on the development network), not the guest's DHCP address.

QEMU manages a bundled Python 3 helper and private GDB Unix socket. Python must
be on PATH. Do not combine `--dbgport` with another `-gdb`/`-s` endpoint.
This integration is tested on Linux; the option rejects Windows hosts.

In ZDS **Debugger / Debug Tool**, select **Ethernet Smart Cable**, IP
`127.0.0.1`, port `4040`. Installed identifiers are `EthernetSmartCable` for
the tool and `ethernetSmartCable` for communications; defaults are in
`config/DefaultDebugTools.xml`. The maintained native CAMEL Debug project already
selects Ethernet Smart Cable; other targets may need adjustment.

Discovery lists `QEMU-eZ80F91`. The SDK broadcasts `scan` to UDP 3000 and receives
`100,QEMU-eZ80F91,02:5A:44:49:HH:LL,PORT`; HH/LL encode the debug port.
This synthetic adapter identity is independent of the guest MAC.

Registers/RAM, run/stop/step and supported flash downloads work through the
bridge. A ZDS reset sequence can change mapping and CPU settings according to
the selected target. The CAMEL GUI workflow has been checked for project opening,
Ethernet connection, OMF695 download and source-level entry halt.

## Original-DLL tests

```sh
python3 tests/test_zds_ethernet.py --native --sdk-scan
python3 tests/test_dbgport.py build/ez80/qemu-system-ez80
```

Requirements: Wine, `i686-w64-mingw32-gcc`, Nexus SDK 1.1 and ZDS II 5.3.5.
`--sdk`, `--zds`, `--qemu` and `--wine-prefix` select other installations.
Tests use temporary files and normally `/tmp/qemuez80f91-zds-wine`.

Checks include connection, DLL register self-test, complete IDE register snapshots
without corrupting BC, target initialization, reset port writes, BC/PC readback,
binary RAM transfers at the lower bound, stepping/events, `LD A,42h`, hardware
breakpoints and asynchronous events, clear/run/status/stop. QMP independently
checks final CPU and RAM. Failures return a nonzero status.

## Protocol and ABI

```text
ZDS II / Nexus API
  → nxEz80EthernetSC.dll
  → TCP 127.0.0.1:4040 (DTL algorithms)
  → tools/zds/ethernet.py + dtl.py + zdi.py
  → private Unix socket (GDB Remote)
  → actual QEMU CPU/memory state
```

Requests have a three-byte header: uint16 little-endian total length and type 0,
followed by a NUL-terminated DTL algorithm. `[]=<hex-length>:` embeds raw blocks,
which may themselves contain NUL. Replies contain type 0, status `00`, four hex
length digits, hex data and NUL. Separate type-1/event-0 packets report breakpoints.

DTL supports variables, registers, expressions, buffers and loops. The bridge
implements the subset required by tested eZ80 algorithms; unknown commands fail.
Firmware update, trace and HALT/SLEEP events are not implemented. Original
internal-F91 and external-AM29LV008BB flash algorithms are tested. Injected ZDI
instructions cover register/port algorithms, not arbitrary Instruction Store
execution. Guest Ethernet uses its own backend, not this debugger channel.

SDK 1.1 headers differ from the installed DLL ABI. The PE32 test uses packing 4,
`nx_Control` vendor fields at byte 100 and the leading `0x470` size expected by
5.3.5 `initializeTarget`. These compatibility adjustments affect only the test
caller; ZDS uses its own matching ABI.

## Private QEMU debugging

Twenty-four little-endian 32-bit slots are exposed in this order:

```text
pc bc de hl ix iy bc_shadow de_shadow hl_shadow spl sps i
 a f a_shadow f_shadow r mbase adl madl iff1 iff2 im ei_delay
```

Private debug addresses `0x1000000 + port` access ports 0000h–FFFFh. They are
outside the guest's 24-bit memory space. QEMU GDB/TCG implements stepping and
breakpoints. A separate manual bridge can be used for diagnosis:

```sh
build/ez80/qemu-system-ez80 \
  -M ez80f91-freertos,ram-boot=on -kernel examples/camelf91/camel.bin \
  -S -gdb tcp:127.0.0.1:1234 -display none -serial stdio -monitor none
# In a second terminal:
python3 tools/zds/ethernet.py --verbose
```

## Flash programming

`./start.sh` loads persistent flash and exposes the debugger at
`127.0.0.1:4040`. Original ZDS RAM loaders erase, program and verify internal
flash and external AMD AM29LV008BB. Target chip-select/memory settings must match
the desired board configuration.

`GET_EMUL_CONFIG` (`.#$`) reports firmware identity and 8192 bytes of transport
buffer. This lets the DLL choose blocks within its 8448-byte receive limit.
Previously empty configuration caused oversized responses and failed RAM checks.
ZDI block reads account for dummy reads and the two-byte-ahead prefetch PC;
GDB writes are split into blocks no larger than 1024 bytes.

```sh
python3 tests/test_zds_flash.py
```

The flash test uses an isolated instance/free port and checks mass erase,
10-KiB programming across RAM blocks, multipart verification, page erase with
neighbors preserved and external AMD erase/program/verify. Saved flash files
are compared byte-for-byte. The 8-KiB RAM workspace is checked without fallback.
Installation paths can be overridden. Restart QEMU after debugger-bridge changes.
