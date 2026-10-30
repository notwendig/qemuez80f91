# Extended eZ80F91 instructions

Implementation milestone: **28 October 2026**. References: UM007715-0415 opcode
maps/tables 106–112 and PS019217-1222 for F91 sleep/interrupt frames. Encodings
are checked independently with the installed ZDS assembler. Normal translation
and address-wrap runtime decoding share the same decoder.

## Added behavior

- DAA, CCF, NEG, RLD/RRD; register/memory/immediate TST and TSTIO.
- IXH/IXL/IYH/IYL loads, eight ALU groups and INC/DEC; indexed-memory INC/DEC.
- BC and `{A,n}` IN/OUT. `IN A,(n)` preserves flags; `IN r,(BC)` sets S/Z/P
  while preserving carry.
- All 28 block-I/O encodings: INI/IND/OUTI/OUTD, INIR/INDR/OTIR/OTDR,
  INIM/INDM/OTIM/OTDM and repeats, INI2/IND2/OUTI2/OUTD2, INI2R/IND2R/OTI2R/OTD2R,
  and INIRX/INDRX/OTIRX/OTDRX.
- LD R,A, LD A,R and LD HL,I.
- Eight RST vectors with mixed SPS/SPL frames; RETN with F91 long-return markers 0/1.
- SLP state: maskable IRQs do not wake the F91 CPU; system reset clears sleep.

The existing index-load error was corrected: **ED31 loads IY from `(HL)`, ED37
loads IX**. ED3E/ED3F stores were already correct.

## Decoder coverage

Counts are valid bytes in unsuffixed opcode spaces, not mnemonics or all
ADL/suffix combinations. The first space excludes eight dispatch bytes.

| Space | Before | After | Newly implemented | Invalid entries removed |
| --- | ---: | ---: | ---: | ---: |
| First opcode, excluding dispatch | 236 | 248 | 12 | 0 |
| ED | 75 | 135 | 60 | 0 |
| DD | 48 | 95 | 48 | 1 |
| FD | 48 | 95 | 48 | 1 |
| CB | 248 | 248 | 0 | 0 |
| DD CB d / FD CB d, each | 31 | 31 | 0 | 0 |

There are 168 added valid encodings with implemented effects. Reserved ED bytes,
undocumented SLL and invalid prefix combinations raise hardware TRAP at vector 0.
ED D2/D3/DA/DB are not RX aliases; DD76/FD76 are invalid, not memory transfers.
`test_illegal_traps.py` checks saved fault addresses and ADL/Z80/MADL frames.

`test_opcode_maps.py` compares all seven spaces against reference sets transcribed
from UM0077, including reserved bytes in both ADL modes. Those sets are not
computed from decoder masks.

## Validation

```sh
python3 tests/test_opcode_maps.py
python3 tests/test_extended_opcodes.py build/ez80/qemu-system-ez80
python3 tests/test_timer_irq.py build/ez80/qemu-system-ez80
python3 examples/extended_opcodes/build.py
python3 tests/test_zds_ethernet.py
```

`test_extended_opcodes.py` runs 195 ROM scenarios and 13 negative cases, including
60000 valid BCD operand/carry combinations for arithmetic plus DAA. Checks cover
registers, flags, RAM/ports, signed/zero/carry boundaries, 16/24-bit counters,
B=0 as 256 iterations, MBASE addressing, 64-KiB/24-bit fetch wrapping and mixed
RST/RETN frames under `-icount shift=0`.

Timer tests demonstrate an IRQ inside INIRX with the partial count and return
PC identifying the unfinished repeat, plus SLP with a pending Timer0 IRQ and
reset. ZDS independently assembles and byte-checks 113 encodings in
`examples/extended_opcodes/opcodes.asm`. Other CPU, memory, firmware and debugger
suites provide additional regression coverage.

## Remaining limits

- This is not exhaustive operand/suffix, silicon or cycle-accuracy validation.
- M-block I/O has partly undefined S/H/PV/C flags; those bits are preserved
  deterministically. Defined Z/N and other documented flags follow eZ80, not
  undocumented classic-Z80 block-I/O rules.
- **LD HL,I:** UM0077 p.195 defines S/Z/H/PV/N changes with carry preserved,
  while the summary/map say unchanged flags. The detailed description is used:
  S from I[15], Z from the 16-bit I value, PV from IFF2. Hardware comparison is
  still needed; the installed simulator's core DLL could not be loaded.
- RETN exists, but NMI sources, watchdog reset and RTC wake-reset are not modeled.
- SLP disables IRQ wakeup, but complete peripheral/oscillator shutdown and analog
  wake/reset timing are not modeled. Debug/system reset remains available.
- Migration is disabled. The private GDB block retains 24 slots;
  `info registers` additionally shows `SLEEP=0/1`.
