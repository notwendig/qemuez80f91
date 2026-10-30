# Development status

Documentation updated **30 October 2026**. Gitlinks, build scripts and fixture
hashes identify source versions. Functional tests do not establish complete
instruction-set or hardware compatibility.

## Implemented and tested

| Area | Evidence |
| --- | --- |
| CPU | Z80/ADL, prefixes, 16/24-bit registers and addresses, stacks, calls/returns, TRAP and extended instructions |
| Memory | Internal RAM/flash/EMAC RAM, CS0–CS3, remapping, priority and AMD flash |
| UART0 | Polling, RX FIFO, interrupts, pin multiplexing and clock gating |
| Timers/IRQs | Timer0/1, vectors, priorities, EI delay, RETI and mode transitions |
| Clock and RTC | Board oscillator/PLL startup, functional lock delay, calendar and ZTP RTC ABI |
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
- Vendor PHY register 18 is incomplete. FreeRTOS may report `10MBPS, HALF_DUPLEX`;
  this is not a measurement of the host network's speed.
- The kit publishes each complete scan without requiring repeated identical
  frames. Mid-scan guest writes may produce mixed rows, as on the latch stream.
- External network tests depend on the bridge, DHCP server and peer. The isolated
  FreeRTOS test uses its own Ethernet socket and does not validate a real LAN.
- ZDS/Nexus/ZTP builds require separately installed vendor tools.
- No complete validation on physical F91 hardware has been performed.

## Next steps

1. Complete vendor PHY speed/duplex diagnostics.
2. Compare more CPU/peripheral cases against independent references or hardware.
3. Exercise additional kernel paths and device combinations with targeted tests.

[Architecture](architecture.md) · [Ethernet](emac.md) · [Kit](kit.md) ·
[CamelForth](camelf91.md) · [Sources](sources.md)
