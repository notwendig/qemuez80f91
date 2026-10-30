# Original FreeRTOS C startup

## Scope

This small probe runs unmodified `cstartup.asm` from the FreeRTOS project and
a test `main()` built by the original Zilog compiler. It computes `0x123456`,
emits `C` on UART0 and halts. Reset repeats the same result. The image is 253
bytes; the reset preparation and test application are new, while startup and
`__frameset` come from the project/vendor runtime. It does not contain the kernel
or complete demonstration application.

Further evidence: [vectors](timer0-interrupts.md), [preemption](freertos-tasks.md),
[blocking/rollover](freertos-blocking.md) and [board/PLL startup](board-startup.md).

## Historical source reference

- Project: [FreeRTOS-eZ80f91](https://github.com/notwendig/FreeRTOS-eZ80f91).
- Original reference commit: `cc64b750e7a5c6dfd19dd8eb3a644a9243ce10a9`.
- Source: `EZ80F910300ZCOG/src/cstartup.asm`.
- SHA-256: `697803471cc7d34f33a011db7fee2f12d482872475189551ae5120210226ff46`.
- Profile: `eZ80F91_99C0879_RAM.ztgt` and the matching application linker map.
- Tools: ZDS II 5.3.5, C compiler 3.4, assembler 4.3, linker 6.25 under Wine.

The reference RAMONLY/CPM22 map places code at zero, DATA at 06B000h,
additional RAM at B80000h–B8FFFFh and stack top at B90000h. The flash target
has different settings. This historical source reference does not select the
current kernel version; see [Sources](sources.md).

## Machine and memory

`ez80f91-freertos` is a functional development-board profile, not an electrical model.

| Range/resource | Mapping |
| --- | --- |
| 000000h–07FFFFh | Lower SRAM startup window on CS1 |
| B80000h–BFFFFFh | Upper SRAM area used by the reference profile |
| Internal flash | 256 KiB, relocated through FLASH_ADDR_U |
| Internal general RAM | 8 KiB at RAM_ADDR_U + offset E000h |
| EMAC RAM | 8 KiB at RAM_ADDR_U + offset C000h |

Current external banks use [dynamic chip-select windows](chip-selects.md),
which supersede the early fixed-window implementation. The model implements
CS0–3 LBR/UBR/CTL (A8h–B3h), BMC (F0h–F3h), RAM_CTL (B4h), RAM_ADDR_U (B5h),
FLASH_ADDR_U (F7h) and FLASH_CTRL (F8h), masking reserved bits. Internal RAM
has priority over internal flash, then external chip selects. Wait-state/bus
fields are stored without cycle timing.

Normal reset uses hardware values. `ram-boot=on` deliberately applies debugger
preparation: CS1=00/07/28, CS2=80/BF/28, internal flash disabled with 60h and RAM
enabled at FFh. This is not a silicon reset state. Use `-kernel` for RAM images
up to 512 KiB and `-bios` for internal-flash boot.

## Run and rebuild

```sh
build/ez80/qemu-system-ez80 -M ez80f91-freertos,ram-boot=on -kernel examples/zds_cstartup/probe.bin -display none -monitor none -serial mon:stdio
```

Expect `C` and HALT. **Ctrl+A, X** exits. Sources, image, linker map and metadata
are in `examples/zds_cstartup/`.

```sh
python3 examples/zds_cstartup/build.py --zds /path/to/ZDSII_eZ80Acclaim!_5.3.5 --freertos /path/to/FreeRTOS-eZ80f91 --out build/zds-probe
python3 tests/test_zds_cstartup.py build/ez80/qemu-system-ez80 build/zds-probe/probe.bin
```

The script copies startup unchanged, logs tool calls, creates Intel HEX and
converts it to raw binary with checksum checking. `probe.json` records source
and binary hashes, commit and linker symbols.

## CPU paths and checks

This path exercises 16/24-bit ALU operations, indexed loads/stores, stack
exchange, EXX/EX AF, LEA, LDI/LDIR, LD A,I / LD I,A / LD I,HL and the C runtime.
LDIR returns to QEMU after each byte, keeping long copies interruptible.
The [LD HL,I flag discrepancy](extended-opcodes.md) remains documented.

Tests cover remapping/enables/priority/reserved bits, SRAM visibility, images
larger than 256 KiB, carry/borrow/half-carry/overflow, negative displacements,
three-byte transfers with guards, register exchange and final copy state.
Dirty BSS is cleared and DATA/computation becomes 123456h, before and after reset.
See [Status](status.md) for current device coverage rather than the original
startup milestone's limitations.
