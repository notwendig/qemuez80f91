# FreeRTOS build and QEMU flash from VSCodium

Open the `qemuez80f91` workspace folder in VSCodium. The ZDS II IDE is not
started. The installed Zilog compiler, assembler and linker still run under
Wine; no editor extension is required for the build tasks.

- **Ctrl+Shift+B → FreeRTOS: Build** builds the selected Release/Debug profile.
- **Tasks: Run Task → FreeRTOS: Rebuild** compiles every source again.
- **FreeRTOS: QEMU-Flash programmieren** builds, cleanly closes the selected
  QEMU/Kit session, backs up its flash and writes/verifies the new images.
- **FreeRTOS: Build, Flash und Kit starten** also opens the Kit and cold boots
  the programmed firmware.
- **FreeRTOS: QEMU stoppen** cleanly closes the Kit/QEMU on port 4040.

Compiler errors are clickable in the Problems panel. Build outputs are separate
from IDE-generated files: `build/firmware/Release/` and `build/firmware/Debug/`.
Each contains `.hex`, `.lod`, `.map`, compiler logs, `compile_commands.json`,
raw internal/external flash and a SHA-256 build manifest. Incremental builds
reuse unchanged objects; project options, target memory settings and headers
are included in dependency checks. No generated ZDS Makefile is required.

## Command line and setup

Python 3, Wine and a local ZDS II eZ80Acclaim 5.3.5 toolchain are required.
`ZDS_HOME` or `--zds` overrides automatic discovery. `WINEPREFIX` or
`--wine-prefix` selects the Wine environment. A fresh checkout needs the
existing `scripts/setup-dependencies.py` workflow before building.

```sh
python3 tools/firmware.py build --config Release
python3 tools/firmware.py build --config Debug --rebuild
python3 tools/flash_firmware.py --config Release --build --stop
python3 tools/flash_firmware.py --config Release --build --stop --run
```

`--bridge none` on the last command runs the Kit offline; the normal bridge is
`br0`. Select another emulator with `--port 4041`. `--directory /path/to/state`
selects its flash working directory; it defaults to this checkout.

## Flash contents and protection

This workflow programs **QEMU's persistent flash images**, not a physical
Ethernet Smart Cable target. The selected emulator must finish flushing its
old flash before replacements are written. Without `--stop`, a running Kit,
occupied debug port or matching QEMU process prevents programming.

The default port 4040 uses:

| File | Memory |
| --- | --- |
| `ez80f91_0.4040` | Internal flash, `000000–03FFFF`, 256 KiB |
| `ez80f91_40000.4040` | External AM29LV008BB, `040000–13FFFF`, 1 MiB |

Both files contain QEMU's four-byte CRC32 trailer. Firmware gaps are erased
bytes (`FF`). Previous files are saved under the selected build directory's
`flash-backups/<UTC timestamp>-<PID>/` before replacement. The builder reads the
project's ROM/RAM ranges and target registers; both configurations retain the
ROM built-in words and the separate dynamic Forth RAM dictionary.

A compilation failure leaves the running emulator untouched. Changed/truncated
build images fail SHA-256 validation before shutdown or flash replacement.

## Using ZDS II alongside VSCodium

The IDE workflow remains available. Open
`subprojects/FreeRTOS-eZ80f91/EZ80F910300ZCOG.zdsproj`, select Debug or Release
and use **Rebuild All**. Both configurations use the flash target. The IDE
regenerates its local workspace/build files and writes Debug outputs to `bin/`
and Release outputs to `Release/` within the subproject. VSCodium continues to
use `build/firmware/`, so their outputs are independent. Close the IDE before
editing the shared `.zdsproj` externally to avoid overwriting settings.
