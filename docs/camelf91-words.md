# CAMELF91 complete dictionary test

The native Debug dictionary contains 237 words. The full run on 29 October
2026 executed every ROM entry and passed 201 stack/result checks. Entry-point
tracing includes indirect compiler/interpreter calls; it does not prove every
possible input or execution path.

## Run

```sh
make -C subprojects/CAMELF91_24
python3 tests/test_camelf91_words.py build/ez80/qemu-system-ez80
```

The runner launches its own QEMU with native `Debug/camel_f91.hex` and its
matching map. It does not use an existing ZDS session on port 4040. `--hex`,
`--map` and `--out` select other artifacts/report directories.

Files under `build/camelf91-words/`:

- `report.md`: per-word results and entry counts.
- `report.json`: machine-readable results, binary SHA-256, addresses and failures.
- `uart.log`: complete console output.
- `entry-trace.log`: evidence for reached entry points.

Wrong results, stalled UART or an unreached entry cause a nonzero exit status.
The dictionary is read from the tested image's linked entries, so newly added
words cannot silently escape coverage.

## Console test file

`examples/camelf91/all-words.fth` contains self-checking Forth code. Send one
line at a time and wait for `OK`; each fits the 124-character input buffer.
Pasting the whole file can overflow the UART receive buffer. `TEST-REPORT` ends with:

```text
TESTS 198 FAILURES 0
```

`examples/camelf91/word_tests.py` supplies both generated Forth and automated
cases. Run it to regenerate the file.

The Python runner adds three interactive KEY/KEY?/ACCEPT checks, checks WORDS,
MEMCFG and DUMP, exercises QUIT/ABORT/ABORT", and checks COLD dictionary restart.
It finally executes `bye` and checks HALT. RESET is reached within COLD; calling
it alone is not a general interpreter restart.

Port words use UART0 scratch register C7h and restore its original value.
Compiler helpers are covered by ordinary definitions and deliberate code fields.

## Formatting regression

`.R` and `D.R` originally omitted negative signs because `D.R` lacked `ROT`
before `SIGN`. The correction is now in the pinned native sources used directly
by both build paths. The separate `test_camelf91.py` suite has 89 cases,
including six added formatting cases with signed and 48-bit boundary values,
all checked before and after reset.
