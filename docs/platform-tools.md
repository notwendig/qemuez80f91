# Native C++ / Qt 6 platform tools

`ez80-platform` implements the UART console, kit matrix/buttons, persistent-flash
starter, CAMEL/ZDS launcher and ZTP demo launcher in C++17 with Qt 6. Sources
are in [`tools/qt/`](../tools/qt/). Linux is the supported host: bridge sysfs,
`flock`, Unix sockets and the installed Wine/ZDS tools retain their roles.

## Build and install

Install a C++17 compiler, CMake 3.21+, Ninja and Qt 6.4+ development packages
for Core, Network, Widgets, Xml and Test. Test is optional with
`-DBUILD_TESTING=OFF`.

```sh
cmake -S . -B build/platform-tools -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/platform-tools
ctest --test-dir build/platform-tools --output-on-failure
python3 tests/test_platform_launch.py
python3 scripts/install.py
```

The QEMU integration test uses temporary flash/disks and requires local
sockets. `scripts/install.py` installs the emulator, Qt executable and
`qemuez80f91` shell entry point. `--platform-tools` selects another Qt binary;
`--prefix` selects the destination. `cmake --install build/platform-tools
--prefix /path` installs only the Qt binary. The source checkout remains
needed for firmware builders and initial disk images. `EZ80_PLATFORM_ROOT`
selects that checkout explicitly.

## Commands

```sh
./start.sh --kit --run
./start.sh --headless --bridge none
tools/platform.sh start --port 4041 --hostname labor-4041 --kit
tools/platform.sh f24 --prepare-only
tools/platform.sh f24
tools/platform.sh demo
tools/platform.sh demo --headless
tools/platform.sh demo --test
tools/platform.sh zds-launch --bios examples/camelf91/camel.bin
tools/platform.sh kit /tmp/ez80f91-1000/4040.kit.json \
    --qmp /tmp/ez80f91-1000/4040.qmp
```

`tools/platform.sh --help` lists all options. The wrapper selects
`EZ80_PLATFORM_TOOLS`, `install/bin/ez80-platform`, then
`build/platform-tools/tools/qt/ez80-platform`. It preserves the working
directory. `QEMU_EZ80` selects QEMU; otherwise checkout install/build paths
are tried before the historical `/tmp/qemuez80f91-build-baseline` path.

The normal console is a Qt window. With `--kit`, UART and the CP/M, Monitor,
CLI and diagnostic terminals share tabs beside the compact matrix/status/button
panel on the right; see [kit terminals](kit.md). The guest address is editable and connections
are opened when their tab is first selected.

Enter sends CR; arrow keys send ANSI sequences. CR, backspace, tabs, cursor positioning and line/screen clearing
work on an 80×40 character screen with scrollback. ANSI foreground/background
colors, bright and 256-color palettes, RGB, bold/dim, italic, underline and
inverse video are supported and preserved in scrollback.
The context menu copies the screen or pastes clipboard text; pasted newlines
become CR. **Ctrl+C in UART** or closing the launcher stops the whole session and saves flash.
Closing the standalone kit leaves the emulator running. Guest-terminal Ctrl+C
goes to CP/M or cancels the current CLI line. `--headless` uses the calling
terminal and restores its terminal settings on exit.

Kit keys **1–3** and mouse press/release operate SW1–3. Focus loss/window
close releases held buttons; SW4 uses QMP `system_reset`. Telemetry refreshes
every 20 ms. Standalone `kit --snapshot preview.png` renders a PNG and exits;
`QT_QPA_PLATFORM=offscreen` permits previews without a display.

The starter retains one persistent lock inode per debug port. QEMU inherits
the locked descriptor so a prematurely killed launcher cannot unlock a live
instance. Existing flash and individual CP/M disk files are preserved. Missing
default disks are initialized from `images/cpm`, or migrated from the legacy
CS3 image after its size is checked. QMP waits for the new bridge port to
reach forwarding before CPU resume. `--bridge none` skips networking for the
persistent-flash starter.

Before setting PHY speed/duplex, the launcher queries the selected QEMU's
EMAC properties through QMP on an empty machine. Older installed builds without
`link-speed`/`full-duplex` keep their EMAC defaults. This also applies to the
demo launcher. To check the actual bridge path without running guest code, use
`python3 tests/test_platform_launch.py --qemu install/bin/qemu-system-ez80 --bridge br0`.

## Python compatibility

The former `tools/start.py`, `tools/kit.py`, `tools/demo.py`,
`tools/zds/f24.py` and `tools/zds/launch.py` command entry points execute the
Qt tools. Python remains needed for firmware builds, dependency setup,
installation and regression scripts. `KitControls` and `tools/demo_network.py`
remain available to existing Python tests/probes.

QEMU's bundled DTL/ZDI/GDB bridge (`tools/zds/ethernet.py`, `dtl.py`, `zdi.py`,
`rsp.py` and their QEMU copies) still runs under Python when `--dbgport` is
used. This migration covers the platform interfaces and launcher logic.
F24 retains build hashes, generated ZDS project/target files, Wine startup
and readiness checks. UART uses a private Unix socket; the old F24
`--uart-port` and `--gdb-port` arguments remain accepted but do not select TCP
ports. `zds-launch` uses QEMU's managed debug service.
