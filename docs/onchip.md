# eZ80F91 on-chip devices and registers

The inventory follows PS019217-1222, Table 3 (pages 27-38): **212 distinct I/O
addresses and 33 aliases** selected by access direction, DLAB or timer/PWM mode.
[`onchip-registers.json`](../tests/fixtures/onchip-registers.json) records every
address and its names. Detailed register tables take precedence over summary
map discrepancies. Undefined reset data has deterministic model values.

| Device | Ports | Functional behavior |
| --- | --- | --- |
| Product ID | 00-02 | Read-only ID 0008h, revision 01h matching ZDI |
| Interrupts | 10-15 | All 46 assigned maskable vectors, two priority levels |
| EMAC | 20-59 | Packet DMA, CRC, filters, IRQs, PHY management/scan, test FIFOs, PAUSE flow control |
| PLL | 5C-5F | Divider, clock mux, protected settings, lock/unlock events and IRQ |
| Timers 0-3 | 60-78 | Four independent 16-bit counters, reload, continuous/one-shot, prescalers, RTC/event clocks and IRQs |
| Capture/compare/PWM | 6A-6E, 79-8B | Four capture inputs, four compare outputs, four PWM pairs, master mode, GPIO gates, edge buffering, dead time and power trip |
| Watchdog | 93-94 | Three clock sources, four periods each, write lock, A5/5A feed, NMI/reset and cause flags |
| GPIO A-D | 96-A7, CE-CF | All 32 pins, open-drain/source, mux, level/single/dual-edge IRQs and acknowledgment |
| Chip selects | A8-B3, F0-F3 | External windows, device types, priority and bus-control register state |
| RAM/MBIST | B4-B7 | Internal RAM remapping/enables; destructive self-tests of both 8 KiB RAM banks |
| SPI | B8-BC | BRG, SSI master, pin-driven slave, all CPOL/CPHA combinations, collisions, mode fault and read-clear status |
| IrDA | BF | Control, UART0 routing, receive enable, decoded-byte loopback |
| UART0/1 | C0-C7, D0-D7 | Independent DLAB/BRG, RX FIFO/timeout, IRQs, loopback, modem deltas, break status and chardevs |
| I2C | C8-CD | SAR/XSAR, data, control/status, CCR, reset, START/repeated START/STOP, ACK/NACK, master and slave |
| Clock power | DB-DC | Peripheral and GPIO gating, all four timer enables |
| RTC | E0-ED | Binary/BCD calendar, locking, alarm, IRQ, clock selection, retention and sleep recovery |
| Flash | F5-FF | Keys, programming/erase/protection, information page, auto-increment and IRQ; FDIV reset 01h |

The F91 has **four** programmable reload timers. EC0/IC0 uses PB0; IC1 uses
PB1, IC2/IC3 PB4/PB5, EC1 PA6, TOUT0/TOUT2 PA4/PA5. Compare/PWM outputs
use Port A. SPI uses PB2 (/SS), PB3 (SCK), PB6 (MISO) and PB7 (MOSI).
UART0 uses Port D; UART1 uses Port C. A second `-serial` attaches UART1.

## Buses and external inputs

The controller buses are named `spi` (SSI) and `i2c`. Example external peers:

```sh
-device at24c-eeprom,bus=i2c,address=0x50,rom-size=256
-device m25p80,bus=spi
```

External-device chip-select wiring belongs to the board/backend. I2C slave
addressing supports both 7-bit and prefixed 10-bit handshakes. QEMU's generic
I2C bus uses 7-bit device addresses; a 10-bit peer must implement the reserved
prefix and second address byte. Multimaster and synchronous slave reads retain
the generic bus framework's limitations.

`gpio-input-a` through `gpio-input-d` are QOM byte properties on the memory
device for external input injection. Individual input/output QEMU GPIO lines
are also available. `kit-buttons` still drives PB0-PB2 active low.

RTC uses vector 06Ch, UART0/1 070h/074h, I2C 078h, SPI 07Ch, GPIO
080h-0FCh and Timer0-3 054h-060h. NMI saves IEF1 in IEF2 independently of
maskable interrupt enables. RETN.L consumes NMI frame markers 02h/03h;
maskable mixed-mode interrupt markers remain 00h/01h.

SLEEP stops the system clock. RTC-clocked timers and watchdog retain their
independent source. RTC alarm and RTC-clocked watchdog reset recover from
SLEEP and record the cause. RC is an ideal 10 kHz source; the RTC peripheral
clock is ideal 32768 Hz or selected 50/60 Hz. MBIST uses a functional 1 ms
completion delay and leaves tested RAM cleared.

## Tests and limits

```sh
python3 tests/test_onchip.py build/ez80/qemu-system-ez80
python3 tests/test_watchdog_nmi.py build/ez80/qemu-system-ez80
python3 tests/test_emac.py build/ez80/qemu-system-ez80
```

The qtest suite reads all 212 addresses, checks 154 defined reset values/masks,
and resets between reads to isolate side effects such as FLASH_DATA advancing
FLASH_COL. It tests actual QEMU SPI NOR and I2C EEPROM peers, an asynchronous
external I2C master, SPI slave modes, GPIO IRQs, timers/capture/compare/PWM,
RTC alarms, watchdog actions, MBIST and EMAC FIFO/scan. CPU-execution tests
cover all eight ADL/MADL/IEF1 NMI combinations and both sleep-recovery sources.

ZDI has a separate debug-register address space. Its bus-control/status and
direct PC memory commands supplement the existing debug operations. OCI trace
and electrical JTAG boundary scan are not simulated. Instruction-store injection
retains the supported opcode subset in the Smart Cable bridge. UART transmit
delivery remains synchronous, IrDA uses decoded bytes, and QEMU VM stop freezes
virtual time. These are functional models, with no electrical, analog or
cycle-accurate silicon compatibility claim.
