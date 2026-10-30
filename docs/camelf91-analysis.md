# CAMELF91 core analysis and fixes

The original defects were reproduced on historical upstream commit
`b975f3acac08c70c05d951aad22e5c1824446206` using ZDS II 5.3.5, the polling
adapter and QEMU. The corrected native sources are now in CAMEL commit
`af47e6520adc220cef5ee7e9ab96f0c336f7e299`; no separate workspace CAMEL patch
is needed. These fixes did not require additional emulator changes.

## Findings

| Area | Reproduction | Original result | Corrected result |
| --- | --- | --- | --- |
| Stack depth | `DEPTH .` on an empty stack | `-267804` | `0` |
| Stack depth | `1 2 3 DEPTH .` | `-267799` | `3` |
| Exact negative division | `-6 3 /MOD . .` | `-3 3` | `-2 0` |
| Negative quotient near zero | `1 -3 /MOD . .` | `0 1` | `-1 -2` |
| Signed 48-bit addition | `0 1 -1 M+ . .` | `1 -1` | `0 -1` |
| Full input buffer | Four characters, `ACCEPT` capacity 4 | Length 3 despite four stored characters | Length 4 |
| Zero-capacity input | `ACCEPT` capacity 0, input XYZ | Length -1 and modified memory | Length 0, unchanged memory |
| Formatting | `-42 6 .R`, `-42 -1 7 D.R` | Missing minus sign | Correct sign and width |

`/MOD . .` prints quotient before remainder; `M+ . .` prints the upper cell
before the lower cell. Original depth values depend on the historical image.

### DEPTH

`S0` is a user variable. The original code used its address rather than its
contents and divided the stack distance by two instead of three. The corrected
expression is `SP@ S0 @ SWAP - 3 /`, including inside compiled words.
Reference: [DEPTH](https://forth-standard.org/standard/core/DEPTH).

### FM/MOD

The original implementation adjusted every negative symmetric quotient,
including exact divisions, and missed zero quotients requiring downward
rounding. Adjustment now occurs only for a nonzero remainder whose sign differs
from the divisor. Existing `/`, `MOD`, `*/` and `*/MOD` definitions inherit
this floored division behavior. Division by zero and unrepresentable quotients
are ambiguous standard cases and are excluded.
Reference: [FM/MOD](https://forth-standard.org/standard/core/FMDivMOD).

### M+

Adding a signed 24-bit cell to a double cell requires sign extension as well
as carry propagation. A negative addend contributes FFFFFF to the upper cell,
equivalent to subtracting one. The fix preserves the sign before adding and
handles sign extension and carry separately, modulo 48 bits.
Reference: [M+](https://forth-standard.org/standard/double/MPlus).

### ACCEPT

The old loop used `start+n-1` and wrote before checking the bound. The corrected
exclusive end is `start+n`; writes occur only below it. Backspace stops at the
start, including address zero. Echo and CR termination remain; excess input
is consumed without storing it.

[ACCEPT](https://forth-standard.org/standard/core/ACCEPT) returns the actual
stored length. Capacity zero is ambiguous in the standard; this project
additionally defines consuming through CR, storing nothing and returning zero.
Guard bytes verify bounds for capacities 0, 1 and 4, excess input and backspace.

### D.R and .R

`D.R` lacked `ROT` before `SIGN`, so the preserved sign below the double cell
was not selected. The shared fix also corrects `.R`. Six formatting cases
expanded the UART regression from 83 to 89 cases.

## Reproduction and metadata

The builder reads corrected sources directly from `af47e65`, enables kit words
and replaces native UART startup with its polling BSP. It checks shared sources,
rejects output directories inside the source checkout and records only known
inputs in `camel.json`. Stale assembly files in an output directory cannot
silently enter the source manifest.

The historical corrected core without kit words was 9353 raw bytes / 9356 ROM
bytes with 432 static RAM bytes. The current kit image is 10688 raw bytes / 10691
ROM bytes with 441 static RAM bytes, plus reserved stacks/work areas. Three ROM
reservation bytes are omitted from raw output.

## Regression coverage

The initial dictionary test on 29 October 2026 executed 226 entries with 197
checks. With kit words, it executes 237 entries with 201 checks. The UART
regression in `examples/camelf91/commands.json` runs all 89 cases before and
after system reset, checking exact responses, dictionary restart, user pointer
and final HALT.

Cases cover empty/nonempty/compiled DEPTH; signed division combinations and
24-bit boundaries; M+ sign/carry behavior; guarded ACCEPT buffers including
address zero; UM* and valid UM/MOD across 24/48-bit ranges; and signed formatting.
Arithmetic vectors were independently computed with Python integers using
seed `0xCAFE91`. These are targeted tests, not exhaustive ANS Forth validation.

A direct-source rebuild reproduces the saved polling image. Historical test
counts describe their original milestones, not a new complete-suite run.
See [Testing](testing.md) and [Validation](validation.md) for current evidence.
