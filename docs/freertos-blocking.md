# FreeRTOS yield, blocking and tick rollover

## Tested behavior

These FreeRTOS V11.3.2 probes extend the [preemption test](freertos-tasks.md)
with voluntary switching, blocking and idle execution. A and B each enter two
nested critical sections and call `taskYIELD()`. On resuming, they check nesting,
disabled interrupts and a local stack value. Leaving the sections restores
interrupts. `BAba` with unchanged ticks proves the voluntary order.

B then starts Timer0 and emits `D`. B sleeps three times for two ticks; A
sleeps for five and then ten ticks. Both leave the ready list, allowing the
lower-priority idle task to record actual ticks. B ends after six ticks.

| Event | Output | Tick relative to timer start |
| --- | --- | ---: |
| Voluntary switches and critical sections | `BAba` | 0 |
| Timer starts | `D` | 0 |
| First B wake | `2` | 2 |
| Second B wake | `4` | 4 |
| A wakes | `5` | 5 |
| Third B wake | `6` | 6 |
| Successful completion | `!` | 6 |

The complete output is `BAbaD2456!`. Tests also check counters A=2/B=4,
idle execution between wakeups, active/saved stack pointers, all three stack
guards, a zero critical counter and disabled interrupts at completion.
The complete sequence repeats after reset.

## 24-bit rollover

`TickType_t` is `uint24_t`. The wrap variant sets `configINITIAL_TICK_COUNT`
to FFFFFCh, exercising delayed-list switching and wakeups across rollover.

| Relative tick | Kernel tick |
| ---: | --- |
| 0 | `FFFFFC` |
| 2 | `FFFFFE` |
| 4 | `000000` |
| 5 | `000001` |
| 6 | `000002` |

The independent uptime counter in `llport.asm` starts at zero and must finish
at six in both variants. Timer0 runs at 1 kHz from a 50-MHz system clock.

## Saved inputs and execution

`examples/freertos_tasks/blocking/` contains sources `main.c`, `boot.asm`,
`FreeRTOSConfig.h`, normal `probe.bin/json/map` and rollover `wrap.bin/json/map`.
Both current raw images are **445033 bytes**. ROM usage is 14324 bytes normally
and 14356 bytes for rollover. Metadata records the kernel commit, patch/source
hashes, symbols and binary hash.

```sh
build/ez80/qemu-system-ez80 -M ez80f91-freertos,ram-boot=on -kernel examples/freertos_tasks/blocking/probe.bin -icount shift=0 -display none -monitor none -serial mon:stdio
python3 tests/test_freertos_blocking.py build/ez80/qemu-system-ez80
```

The test runs both variants and reset by default. A second argument selects
one image. Replace `probe.bin` with `wrap.bin` for interactive rollover.
**Ctrl+A, X** exits QEMU after HALT.

## Rebuild

Use the documented ZDS/project sources and a V11.3.2 kernel checkout:

```sh
python3 examples/freertos_tasks/build.py --scenario blocking --zds /path/to/ZDSII_eZ80Acclaim!_5.3.5 --freertos /path/to/FreeRTOS-eZ80f91 --kernel /path/to/FreeRTOS-Kernel --out build/freertos-blocking
python3 examples/freertos_tasks/build.py --scenario wrap --zds /path/to/ZDSII_eZ80Acclaim!_5.3.5 --freertos /path/to/FreeRTOS-eZ80f91 --kernel /path/to/FreeRTOS-Kernel --out build/freertos-wrap
python3 tests/test_freertos_blocking.py build/ez80/qemu-system-ez80 build/freertos-blocking/probe.bin
python3 tests/test_freertos_blocking.py build/ez80/qemu-system-ez80 build/freertos-wrap/probe.bin
```

Without `--scenario`, the builder selects preemption. The wrap variant changes
only the copied configuration's initial tick. Original assembly and the kernel
checkout remain unchanged. The three scenarios were rebuilt and tested with
V11.3.2; this does not claim byte identity with the older V10.6.1 fixtures.

This reduced probe does not exercise queues, semaphores, dynamic task creation
or software timers. The [full application](../subprojects/FreeRTOS-eZ80f91/BUILD.md)
and its isolated network test cover additional paths.
