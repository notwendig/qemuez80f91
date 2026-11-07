# Launch CAMEL24 in ZDS II

From the project directory:

```sh
tools/platform.sh f24
```

The launcher builds corrected CAMEL sources with line information and OMF695
symbols, creates `build/f24/`, starts QEMU in the tested
`ez80f91-freertos,ram-boot=on` profile and starts the Ethernet/ZDI bridge.
It opens ZDS II, selects Ethernet Smart Cable at `127.0.0.1:4040`, loads
`camel.lod` and stops at `_main` in `CAMLF91e.asm`. Readiness requires a successful
ZDS script response. UART is connected to the launcher's application console.

| Key | Action |
| --- | --- |
| F5 | Run |
| F11 | Step Into |
| F10 | Step Over |
| Ctrl+F5 | Stop |
| Ctrl+Shift+F5 | Reset |

After F5, enter Forth commands in the console. **Ctrl+C** stops the launched
processes. A lock prevents a second launch in the same output directory.

Wine and the installed ZDS assembler/linker are required. The view helper
also requires `i686-w64-mingw32-gcc`; Nexus DLL tests are separate. The default
ZDS directory is `~/.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5`; build/IDE
processes use `/tmp/qemuez80f91-zds-wine` without modifying the installation.

```sh
tools/platform.sh f24 --rebuild
tools/platform.sh f24 --prepare-only
tools/platform.sh f24 --qemu /path/qemu-system-ez80 --zds /path/ZDSII
```

Build the [Qt platform tools](platform-tools.md) first. `QEMU_EZ80` and
`ZDS_HOME` override defaults. QEMU is selected from `install/bin`, then
`build/ez80`, then the historical `/tmp/qemuez80f91-build-baseline` fallback.
TCP 4040 (debugger) and UDP 3000 (discovery) must be available.
UART uses a private Unix socket and a native Qt terminal. The bridge uses
`--dbgport=4040` and a private GDB Unix socket. `--gdb-port` and `--uart-port`
remain accepted compatibility arguments; they no longer select TCP endpoints.
Stop an older manually started bridge first.

Logs in `build/f24/`: `zds-session.log`, `qemu.log`, `ide.log`, `build.log` and
`views.log`. UART and QMP paths are under `/tmp/ez80f91-<uid>/4040.*`.
The IDE script is `start.cmd`. Generated targets disable
`externalAutoSelect` because the RAM profile has no external flash to identify.

The GUI workflow was checked on 28 October 2026: project opening, Ethernet
connection, OMF695 download, source display and halt at entry (PC 00039Bh).
The debug raw image matched the image covered by 89 UART cases. See
[ZDS integration](zds-ethernet.md) for the scope of this evidence.

## IDE views

The helper opens Registers, Special Function Registers, Clock, Memory, Watch,
Locals, Call Stack, Symbols, Disassembly and Simulated UART Output. It reuses
existing views, reads command IDs from installed IDE accelerator resources,
selects the Memory address space and maximizes the source window. Disable it
with `--no-views`.

Clock may report `not supported` through Ethernet Smart Cable. Simulated UART
Output is the IDE simulator view, not QEMU UART. Forth I/O uses the application
console. Locals/Call Stack require suitable frame/debug information; Watch
needs explicitly added expressions.

The installed Nexus GET_REGS_ALL algorithm uses `R16=16` when restoring AF/MBASE.
The bridge handles this as an AF-read compatibility case, not a new silicon ZDI feature.

## Guest Ethernet and external banks

`--nic` forwards a QEMU network backend, for example
`tools/platform.sh f24 --nic 'socket,connect=127.0.0.1:5555'`.
This launcher's default is `none`; the peer must speak QEMU's Ethernet socket
protocol. CAMEL still needs its own guest network driver/stack.
See [EMAC](emac.md).

`--cs0` through `--cs3` select `ram`, `flash` or `none` at startup. Firmware
then controls windows and enables through F91 registers. Defaults are CS0 flash,
CS1–3 RAM. See [Chip selects](chip-selects.md).
