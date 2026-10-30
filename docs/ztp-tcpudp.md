# Original ZTP 2.5.1 TCPUDPDemo

The locally installed example runs its original RZK kernel, UART/MAC drivers
and ZTP stack. Tested behavior includes DHCP, UART shell login, exact 1000-byte
UDP echo and 4000-byte TCP echo through real host sockets. The expected external
DHCP server is **nadibox (192.168.77.1)**; the tools do not provide a replacement.
The guest received 192.168.77.16 during the reference run, but its address is
always taken from the lease rather than fixed in the launcher.

The full echo test uses the vendor-supported RAM filesystem. External AMD flash
is available through [chip selects](chip-selects.md), but a complete external-ZFS
startup is not an established reference scenario.

## Application console

```sh
python3 -m tools.demo
```

The launcher builds the RAM image if needed and uses the existing bridge helper
with `br0`. UART runs in the calling terminal. Log in as `anonymous` / `anonymous`;
use `help`, `bsdudpserver` and `bsdtcpserver`. **Ctrl+C** or **Ctrl+]** stops QEMU
and restores terminal settings.

```sh
python3 -m tools.demo --test           # automatically test DHCP + 1000-byte UDP + 4000-byte TCP
python3 -m tools.demo --rebuild        # rebuild and open the console
python3 -m tools.demo --prepare-only   # prepare the image only
python3 -m tools.demo --seconds 20     # close the console after 20 seconds
```

`--qemu`, `--zds`, `--out`, `QEMU_EZ80` and `ZDS_HOME` select tools/output.
A directory lock prevents concurrent launchers. `--bridge`, `--bridge-helper`
and `--dhcp-server` select the existing bridge/helper and expected server address.

The development host uses 192.168.77.3 on br0, with enp0s25/enp6s0 physical ports
and `/usr/libexec/qemu-bridge-helper` authorized for br0. These are environment
examples, not settings applied by the launcher. It waits for the new TAP port
to reach STP forwarding before starting the guest, then closes that temporary
port at exit.

Captured DHCP ACKs must match guest MAC 00:90:23:00:01:01 and the expected server;
a different server aborts the run. There is no local-server fallback. `--test`
uses normal host UDP/TCP sockets over the same LAN; it does not open ZDS II.

Output includes `uart.log`, `qemu.log`, `devices.log`, `network.pcap` and
`network.json`. The latter records server/lease and, for tests, `dhcp_verified`,
`udp_echo_ok` and `tcp_echo_ok`.

## Reproduce the complete test

```sh
python3 examples/ztp_tcpudp/build.py --filesystem ram --out build/ztp-tcpudp-ram
python3 examples/ztp_tcpudp/probe.py --out build/ztp-tcpudp-ram --seconds 30 --tcp-test --expect-dhcp
```

The builder uses the installed project
`ZTP2.5.1/ZTP/SamplePrograms/TCPUDPDemo/ZTP_TCPUDP_DEMO_eZ80F91_99C0879-AMD.zdsproj`
under the default ZDS 5.3.5 directory, or `--zds`. It compiles 23 sample sources
with their definitions/libraries and generates HEX, OMF695, map and raw image.
The tracked `examples/ztp_tcpudp/ram.linkcmd` supplies a 50-MHz oscillator/RAM
profile without requiring a previously generated SDK linker file.
`--memory-profile qemu` adjusts chip-select/flash parameters.

Vendor files remain untouched. Source copies/products stay in ignored `build/`
and are not distributed. The RAM variant changes only the provided
ZFS_USES_XFL/ZFS_USES_RAM switches in copied `ZFS_Conf.c`. Its volume occupies
internal RAM B7F000h–B7FFFFh; application/thread stacks use external SRAM.
The shell, networking code and libraries are not replaced.

The recorded RAM build produced 187794 raw bytes and used 111578 application-RAM
bytes. The original flash-filesystem variant produced 188039 raw bytes and used
114762 application-RAM bytes. Actual rebuild maps remain authoritative.

The probe also uses the bridge and expected nadibox DHCP. `--tcp-test` runs UDP
first, then TCP. It supplies the original login, server commands and ports
4000/4001 through UART, waiting briefly after the first prompt for command
registration. The guest address comes from the ACK. `--udp-test` selects UDP only;
without either option, UART is logged but not driven automatically.

`--expect-dhcp` requires `DHCP OK` and a matching ACK. Legacy `--dhcp` is accepted
but starts no server. The former 172.16.6.1 simulation is removed. `probe.json`
records CPU/MAC snapshots, leases and results; `network.pcap` records complete
frames. These are connection tests, not load tests.

## Separate flash-filesystem experiment

```sh
python3 examples/ztp_tcpudp/build.py
python3 examples/ztp_tcpudp/probe.py --seconds 30 --expect-dhcp
```

This reaches `DHCP OK`, `Initializing network stack`, then
`Formatting the Invalid Volume : EXTF`. The linker profile disables CS0; external
flash needs the appropriate enabled window. The flash information page is
implemented and survives system reset, but not process restart. Internal main-array
programming/erase is also now implemented; see [Flash/UART](flash-uart.md).

## Profiles and historical fixes

The QEMU profile selects lower SRAM on CS1, upper SRAM on CS2 and FLASH_CTL=60h,
keeping RAM code visible during original startup; RAM_ADDR_U remains B7h.
The tracked RAM template selects a 50-MHz oscillator without PLL. The diagnostic
probe's machine argument currently specifies a 5-MHz oscillator and PHY address
31; distinguish this from linker clock definitions when comparing timing.
`--memory-profile vendor` retains the installed template and may not match
QEMU's RAM startup preparation.

`-icount shift=5,sleep=off` assigns 32 ns per instruction, preventing real-time
timer pressure from overwhelming the slow interpreter during RZK startup.
`--icount` selects another shift; this is not accurate CPU-cycle timing.

Historical failures included MLT retaining a stale upper byte, producing an
invalid RZK scheduler index/stack. The result is now limited to 16 bits and tested.
UM0077 leaves the upper byte unclear; independent hardware evidence is absent,
and the installed simulator core could not be loaded. Information-page erase
and UART FIFO/IRQs were subsequently implemented for the original drivers.

`--break-at 0x...` and `--trace-steps ...` support diagnosis. Always take addresses
from the matching image's map; RAM and flash-filesystem builds differ.

## ZDS debug port and discovery

```sh
python3 -m tools.demo --dbgport=4040
```

This enables Ethernet Smart Cable and UDP 3000 discovery, pausing the CPU until
ZDS Run. DHCP begins only after Run. Use the host IP (locally 127.0.0.1), not the
guest address. This mode cannot be combined with `--test`.
See [Debugger protocol](zds-ethernet.md).
