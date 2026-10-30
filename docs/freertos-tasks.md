# Two preemptive FreeRTOS tasks

## Tested behavior

The probe runs **FreeRTOS V11.3.2**, pinned to
`8a59a4b19bf72977819feddef87d41163ced7004`, with `kernel-V11.3.2.patch` from
`notwendig/FreeRTOS-eZ80f91`. It uses original `cstartup.asm`, `vectors24.asm`,
`llport.asm`, `portmacro.h` and the project's standard integer header.
Static-memory callbacks use `configSTACK_DEPTH_TYPE`, as required by FreeRTOS 11.
Exact inputs and hashes are recorded in `examples/freertos_tasks/probe.json`.

Two equal-priority static tasks count four iterations each and emit A or B on
UART0. They busy-wait for the kernel tick to change; neither yields nor delays.
Timer preemption alone switches tasks. Expected output is `BABABABA!`, then
DI/HALT. The kernel performs creation, ready-list management, scheduler startup,
`xTaskIncrementTick` and `vTaskSwitchContext`.

The original vector wrapper saves registers; `switch` in `llport.asm` stores
the old SP in its TCB and loads the next task's SP. An idle task exists but is
not scheduled while both higher-priority tasks remain ready.

Tests check seven timer ticks, counters of four, exact UART output, both saved
TCB stack pointers, active CPU stack and stack guards. The entire run is repeated
after system reset.

## Minimal application port

`main.c` contains only initial stack frames, critical sections, Timer0 startup
and static-memory callbacks. Three stacks have 512 24-bit words each (1536 bytes).
The full application `port.c`, networking, uzlib and heap setup are not linked.
Software timers and dynamic allocation are disabled. The basic probe uses the
already tested RAM-boot preparation; [board startup](board-startup.md) tests
the complete original clock/memory initialization separately.

`llport.asm` reserves an unused 64-KiB CP/M area at B80000h. The initial stack
is B90000h, and the linker RAM extends to BFFFFFh. The current saved raw image
is **444857 bytes**; its ROM allocation is 13078 bytes. Address gaps, not just
code size, determine the raw file length.

## Run and rebuild

```sh
build/ez80/qemu-system-ez80 -M ez80f91-freertos,ram-boot=on -kernel examples/freertos_tasks/probe.bin -icount shift=0 -display none -monitor none -serial mon:stdio
python3 tests/test_freertos_tasks.py build/ez80/qemu-system-ez80
```

Press **Ctrl+A, X** to exit QEMU after HALT. Use the public V11.3.2 kernel tag;
no unpublished library commit is required.

```sh
git clone https://github.com/FreeRTOS/FreeRTOS-Kernel.git /tmp/ez80-freertos-kernel
git -C /tmp/ez80-freertos-kernel checkout V11.3.2
python3 examples/freertos_tasks/build.py --zds /path/to/ZDSII_eZ80Acclaim!_5.3.5 --freertos /path/to/FreeRTOS-eZ80f91 --kernel /tmp/ez80-freertos-kernel --out build/freertos-tasks
python3 tests/test_freertos_tasks.py build/ez80/qemu-system-ez80 build/freertos-tasks/probe.bin
```

The builder reads `tasks.c` and `list.c` from the pinned commit and applies
relevant project fixes in the output directory. It does not alter the kernel
checkout. Wine requires local Unix sockets; the tools come from ZDS II 5.3.5.

## CPU instructions exercised

- Accumulator rotations preserving S/Z/PV and clearing H/N.
- PEA IX/IY with signed offsets and short/long stacks.
- LD A,(BC/DE), LD (BC/DE),A and indexed register/memory transfers.
- MLT BC/DE/HL/SP, limiting the result to a 16-bit product with zero upper byte.
- Immediate ADD/ADC/SUB/SBC and their documented flags.

References include UM007715-0415 pp. 206–211, 246–247 and 275–276.
`test_cstartup_ops.py` provides targeted regressions. [Blocking and rollover](freertos-blocking.md)
and [board/PLL startup](board-startup.md) extend this probe. None of these
establish complete CPU or cold-flash compatibility.
