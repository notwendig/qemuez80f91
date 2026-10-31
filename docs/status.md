# Development status

Documentation updated **31 October 2026**. Gitlinks, build scripts and fixture
hashes identify source versions. Functional tests do not establish complete
instruction-set or hardware compatibility.

## Implemented and tested

| Area | Evidence |
| --- | --- |
| CPU | Z80/ADL, prefixes, 16/24-bit registers and addresses, stacks, calls/returns, TRAP and extended instructions |
| Memory | Internal RAM/flash/EMAC RAM, CS0–CS3, remapping, priority and AMD flash |
| On-chip registers | All 212 I/O addresses catalogued; 154 reset values/masks checked; [device coverage](onchip.md) |
| UART0/1 and IrDA | RX FIFO, interrupts, DLAB, mux, clock gating, decoded-byte loopback and modem deltas |
| Timers/IRQs | Timer0-3, event/capture/compare/PWM, priorities, EI delay, RETI/RETN and mode transitions |
| SPI/I2C | Real SSI NOR and I2C EEPROM transfers, SPI slave modes, externally addressed I2C slave |
| Watchdog and RTC | Feeding, NMI/reset causes, clock sources, calendar/alarm IRQ, SLEEP recovery |
| Clock | Board oscillator/PLL startup, lock delay, clock mux and SLEEP system-clock stop |
| Ethernet | Shared-RAM descriptors, TX/RX, overflow, filters, interrupts and Clause-22 management |
| Debugger | Original ZDS EthernetSC DLL, registers/RAM, run/stop/step, breakpoints, flash and discovery |
| Kit | 5×7 matrix, complete-scan publication, SW1–3 and reset |
| CamelForth | Corrected core; 237 executed dictionary entries, 201 checks and 89 cases before/after reset |
| FreeRTOS | V11.3.2; original C/board startup, task switching, blocking, critical sections and 24-bit rollover |
| FreeRTOS networking | Plus-TCP V4.4.2; isolated DHCP, ARP, ICMP and TCP-console tests; full-width IPv4 diagnostics |
| CP/M 2.2 | uzlib `6d60d65`, gzip disk, CRC/size error tests, BIOS TRAPs and a separate live console test |
| ZTP | Original RAM-filesystem example, nadibox DHCP and UDP/TCP echo |

See [Validation](validation.md) for dated evidence and [Testing](testing.md)
for local, SDK-dependent and live test requirements.

## Known limits

- No complete instruction/peripheral compatibility claim, cycle-accurate CPU,
  electrical bus model or analog LED simulation.
- UART transmit/baud timing and many register/interrupt combinations remain untested.
- PHY speed/duplex diagnostics follow the configured host-derived 10/100 mode;
  the F91's 100 Mbps limit and functional packet model still apply.
- The kit publishes each complete scan without requiring repeated identical
  frames. Mid-scan guest writes may produce mixed rows, as on the latch stream.
- External network tests depend on the bridge, DHCP server and peer. The isolated
  FreeRTOS test uses its own Ethernet socket and does not validate a real LAN.
- ZDS/Nexus/ZTP builds require separately installed vendor tools.
- No complete validation on physical F91 hardware has been performed.

## Next steps

1. Validate more device combinations against independent hardware traces.
2. Compare more CPU/peripheral cases against independent references or hardware.
3. Exercise additional kernel paths and device combinations with targeted tests.

[Architecture](architecture.md) · [Ethernet](emac.md) · [Kit](kit.md) ·
[CamelForth](camelf91.md) · [Sources](sources.md)
