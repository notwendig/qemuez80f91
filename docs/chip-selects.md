# Dynamic external memory windows: CS0–CS3

Both machine profiles derive external mappings from CSx_LBR, CSx_UBR and
CSx_CTL. Fixed windows at 000000h and B80000h are no longer a requirement.

## Selecting RAM or flash

Registers select address, memory/I/O mode and enable; the attached device type
is a board setting chosen at launch.

| Option | Default | Device |
| --- | --- | --- |
| `cs0` | `flash` | 1-MiB bottom-boot AMD NOR |
| `cs1` | `ram` | RAM |
| `cs2` | `ram` | RAM |
| `cs3` | `ram` | RAM |

Each accepts `ram`, `flash` or `none`:

```sh
qemu-system-ez80 -M ez80f91-freertos,ram-boot=on,cs0=flash,cs1=ram,cs2=ram,cs3=flash -kernel image.bin
```

```sh
python3 -m tools.demo --cs3 flash
python3 tools/zds/f24.py --cs3 flash
```

The diagnostic probe accepts the same options. Device type remains fixed during
a VM run; firmware may reprogram windows at any time. An enabled higher-priority
`none` bank still hides lower-priority banks: reads return 00h and writes are ignored.

## Registers and priority

A memory window is active when CTL bit 3 (EN) is set, bit 4 (IO) is clear and
UBR is at least LBR:

```
Start = LBR << 16
End   = ((UBR + 1) << 16) - 1
Size  = (UBR - LBR + 1) * 64 KiB
```

Equal bounds enable one 64-KiB page. Example for CS3:

```
OUT0 (B3h), 00h    ; disable the window
OUT0 (B1h), 60h    ; LBR
OUT0 (B2h), 63h    ; UBR
OUT0 (B3h), 08h    ; enable memory window 600000h–63FFFFh
```

Every write updates mapping immediately. Disable a bank while changing bounds
if temporary overlap could hide running code. IO selection removes the memory
window; external I/O devices are not attached by this model. Invalid bounds disable it.

Priority is internal RAM (including EMAC RAM), internal flash, CS0, CS1, CS2,
then CS3. Disabling a window exposes the underlying mapping.

## Contents and AMD protocol

Each RAM bank reserves a stable virtual 16-MiB area, allocating host pages on
demand. Window offset zero is bank offset zero: moving a window exposes the
same bytes; shrinking preserves hidden contents. Initial RAM is zero.

Flash uses QEMU `pflash_cfi02`: 8-bit AMD NOR, IDs 01h/37h, 1 MiB with sectors
16 KiB, 2×8 KiB, 32 KiB and 15×64 KiB, matching AM29LV008BB geometry. The generic
model also exposes CFI. Larger windows mirror at 1-MiB intervals; smaller ones
expose only part of the chip.

Tests cover unlock addresses 555h/2AAh, IDs, NOR byte programming, sector erase
and CFI QRY. RAM-style writes are not programming commands. Fresh flash is FFh.
RAM/flash survive disabling, remapping and system reset. Process persistence
is implemented as described in [Flash files](flash-uart.md), including deferred
external-file attachment after a valid CS enable.

For writable raw CP/M disks, attach a file to CS3 RAM:

```sh
qemu-system-ez80 -M ez80f91-minimal,cs3-file=/absolute/path/to/cs3-abcdij.img
```

`cs3-file` requires `cs3=ram` and accepts a nonempty file up to 16 MiB.
It loads once at startup, preserves bank contents across remapping/reset,
and saves exactly the original raw length on orderly exit, without a CRC
trailer. Bytes beyond the file start at zero and are not persisted.
Firmware controls the address window. The updated CP/M firmware uses
200000h–AFFFFFh for A/B/C/D/I/J and narrows CS2 before heap initialization
to avoid hiding the disk. See [disk layout](../images/cpm/README.md).

Internal main flash and its information page are separate devices. Wait states
and external bus signals are not cycle-accurate. The generic bank-offset mapping
does not infer arbitrary physical address wiring.

## Startup profiles and tests

Normal reset retains CS0=00h–FFh/CTL=E8h and CS1–3 disabled. Explicit RAM boot
disables CS0, maps CS1 to 000000h–07FFFFh and CS2 to 800000h–BFFFFFh. This avoids
hiding running SRAM with empty flash during original startup. Guest register
writes then control all subsequent mappings.

```sh
python3 tests/test_chip_selects.py build/ez80/qemu-system-ez80
```

Thirteen scenarios test RAM/AMD flash at every CS, bounds, resizing, enable,
IO selection, invalid bounds, priority including empty banks, CFI and reset
retention. Original-DLL flash tests provide separate integration evidence.
The ZTP RAM-filesystem demonstration also passed real-network DHCP/UDP/TCP tests.

The ZTP linker profile still disables CS0. Full external-ZFS startup needs a
suitable flash window and is not an established reference test; the normal demo
continues to use its tested RAM filesystem.
