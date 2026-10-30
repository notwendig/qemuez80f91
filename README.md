# qemuez80f91

Development environment for the **Zilog eZ80F91**: QEMU system emulation,
ZDS II debugging, CamelForth, FreeRTOS, Ethernet, CP/M and the development-kit display.

The emulator runs actual eZ80 firmware in Z80 and ADL modes. It focuses on
functional behavior and reproducible regression tests. It is not cycle-accurate
or bus-accurate and does not establish complete eZ80F91 hardware compatibility.

## Projects

| Component | Purpose | Documentation |
| --- | --- | --- |
| QEMU/eZ80F91 | CPU, memory, flash, UART, timers, RTC, Ethernet and kit | [Architecture](docs/architecture.md), [Getting started](docs/getting-started.md) |
| CAMELF91_24 | Corrected 24-bit Forth, buttons and 5×7 matrix | [Project](https://github.com/notwendig/CAMELF91_24), [Integration](docs/camelf91.md) |
| ez80f91bsp | Assembly library for native CAMEL builds | [Project](https://github.com/notwendig/ez80f91bsp) |
| FreeRTOS-eZ80f91 | RTOS, TCP/IP, CP/M 2.2 and kit demonstration | [Project](https://github.com/notwendig/FreeRTOS-eZ80f91), [Build](subprojects/FreeRTOS-eZ80f91/BUILD.md) |
| ZTP TCPUDPDemo | Build and run the installed vendor example | [TCP/UDP](docs/ztp-tcpudp.md) |
| Debugger and tests | Ethernet Smart Cable, discovery and regression tests | [ZDS II](docs/zds-ethernet.md), [Tests](docs/testing.md) |

## Quick start

```sh
git clone https://github.com/notwendig/qemuez80f91.git
cd qemuez80f91
python3 scripts/setup-dependencies.py
```

The setup command also downloads the nested BSP, kernel, TCP/IP and uzlib
sources and applies the required compatibility patches. A plain clone or
outer-submodule initialization alone is not enough to build the ZDS firmware.

Build the pinned QEMU release with the supplied eZ80 patch:

```sh
git clone --depth 1 --branch v11.1.2 https://gitlab.com/qemu-project/qemu.git qemu
sh scripts/apply-qemu-patches.sh
mkdir -p build/ez80
cd build/ez80
../../qemu/configure --target-list=ez80-softmmu --disable-docs --disable-werror --without-default-features --enable-tcg --enable-system --disable-tools
ninja -j8 qemu-system-ez80
cd ../..
export QEMU_EZ80="$PWD/build/ez80/qemu-system-ez80"
python3 tests/test_smoke.py "$QEMU_EZ80"
```

See [Getting started](docs/getting-started.md) for dependencies, operation
without networking, local installation and optional ZDS tools.

## Operation

```sh
./start.sh                 # UART terminal; CPU waits for ZDS II
./start.sh --kit           # also open the matrix/button window
./start.sh --run --kit     # start saved flash immediately
./start.sh dbgport 4041    # separate instance on another debug port
```

These launchers use the existing `br0` bridge. They do not create a DHCP server;
**nadibox** supplies DHCP on the development network. The CPU starts only after
the TAP port enters forwarding state. A ROM can also run without a bridge:

```sh
"$QEMU_EZ80" -M ez80f91-minimal -bios examples/hello_uart0.bin \
  -display none -monitor none -serial mon:stdio -nic none
```

Press **Ctrl+A, X** to exit the direct QEMU command. In the launcher UART
terminal, **Ctrl+C** stops the instance and saves its flash contents.

### CamelForth

```sh
python3 tools/zds/f24.py
```

The launcher builds a separate copy and opens ZDS II with source debugging.
Press **F5** to run, then enter commands in the UART console:

```forth
1 2 + .
BUTTONS .
CHAR A MATRIX-CHAR
MATRIX-OFF
```

See [ZDS launch](docs/start-f24.md), [Kit words](docs/camelf91-kit.md) and
[Dictionary tests](docs/camelf91-words.md). The dictionary contains 237 words;
the full test makes 201 result checks. Another 89 cases run before and after reset.

### FreeRTOS and ZTP

CP/M uses raw writable A/B/C/D/I/J disk images on CS3, without startup
decompression. The [disk layout and build instructions](images/cpm/README.md)
describe the image formats. `start.sh` initializes a separate persistent
`ez80f91_cs3.<debugport>` image from the bundled template on first use.

```sh
python3 subprojects/FreeRTOS-eZ80f91/setup-dependencies.py
python3 -m tools.demo --prepare-only
```

Build FreeRTOS in `EZ80F910300ZCOG.zdsproj`, configuration **Debug** or
**Release**. Debug uses RAM. Release places code in internal flash and the compressed CP/M
disk image in external AMD flash at `0x100000`.
Its dependencies are FreeRTOS-Kernel **V11.3.2**, FreeRTOS-Plus-TCP **V4.4.2**
and uzlib commit **6d60d65**. ZDS compatibility changes are supplied as patches.
`python3 -m tools.demo` runs the installed ZTP TCP/UDP example instead.
Both require the appropriate [ZDS and network setup](docs/getting-started.md).

## Data and configuration

- `QEMU_EZ80`: path to the emulator executable.
- `ZDS_HOME`: ZDS installation; default `~/.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5`.
- Debugger: host TCP 4040; Scan Device: host UDP 3000. The debugger uses the
  host address, independently of the guest's DHCP address.
- Runtime logs and QMP socket: `/tmp/ez80f91-<uid>/<port>.*`.
- Persistent flash: `ez80f91_0.<port>` and external images in the working
  directory. These files are user data, not disposable build products.
- `build/`: generated files and reports. `examples/`: tracked sources and
  selected test images with metadata.

## Documentation and development

[Documentation index](docs/README.md) · [Status and limits](docs/status.md) ·
[Development](docs/development.md) · [Sources and licenses](docs/licenses.md)

Maintained documentation uses English throughout. The complete QEMU changes
are stored in `patches/0001-ez80f91-minimal.patch`. The local QEMU checkout
and vendor SDKs are not distributed. Each subproject retains its own Git
history and licensing notices.
