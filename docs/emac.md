# eZ80F91 Ethernet MAC

Both machines expose `ez80f91-emac`, connecting I/O 0020h–0059h and 8 KiB of
shared Ethernet RAM to a QEMU backend. The reference is PS019217-1222 pp. 287–333.
The implementation does not incorporate vendor ZTP driver code.

## Backend connection

```sh
python3 tools/zds/f24.py --nic 'socket,connect=127.0.0.1:5555'
```

A QEMU-compatible peer must already listen on port 5555. Alternatively:

```sh
python3 tools/zds/f24.py --nic 'socket,listen=127.0.0.1:5555'
```

For a direct QEMU command, append the backend to its machine/image/UART options:

```sh
-nic socket,connect=127.0.0.1:5555,model=ez80f91-emac
```

Frames use a four-byte network-order length followed by Ethernet bytes without
preamble/FCS. An ordinary TCP echo server is not a compatible peer. Other QEMU
backends are available if compiled in. This project's minimal build has no
Slirp, so `-nic user` is unavailable.

`tools/zds/f24.py` defaults to `--nic none`; registers/RAM remain present but
PHY link is down. By contrast, `start.sh` uses the existing `br0` bridge through
the bridge helper; see [Getting started](getting-started.md). Debugger TCP 4040
and UART TCP 4444 are independent of guest Ethernet. CAMEL does not gain a
network stack merely by selecting a backend. [ZTP](ztp-tcpudp.md) and the
[FreeRTOS network test](testing.md) exercise actual guest stacks.

## Guest programming

1. Set EMAC_RST=3Fh, boundaries and software RRP.
2. Partition TX `[TLBP, BP)` and RX `[BP, RHBP)`. RHBP=0 means offset 2000h.
   Pointer registers hold 32-byte-aligned offsets; BUFSZ selects 256/128/64/32 bytes.
3. Set STAD0–5 in network byte order, CFG1, CFG4.RXEN and AFR.
4. Release reset and enable desired IEN bits.
5. Write TX descriptors/payload, then ownership last; write PTMR. PTMR=0
   checks once, while positive values poll every `256 * PTMR` system clocks.
6. Consume RX descriptors, update RRP and acknowledge ISTAT bits with ones.

Descriptors contain seven little-endian bytes: 24-bit NP, 16-bit packet length
and 16-bit status. NP is a full CPU address, not an offset; payload begins at
byte 7. TX requires status bit 15 and clears ownership on completion. Pointers
stay within their partition and payload may wrap. Invalid TX pointers set
TxFSMERR and require TX reset.

With CRCEN, TX length excludes FCS; without it, the guest supplies valid FCS.
Invalid FCS aborts TX instead of forwarding corrupt data. PADEN+CRCEN pads to
60 bytes excluding FCS. RX length includes four generated FCS bytes in RAM.

RX reserves one block to distinguish full from empty. Overflow writes a final
RxOVR descriptor without RxOK and sets RXDONE/RX_OVR. This lets the original
Zilog driver detect overflow without a separately enabled overflow IRQ. Frames
are dropped until explicit acknowledgment. ERAM_EN/RAM_ADDR_U apply to MAC
access; BP_U is a read-only mirror of RAM_ADDR_U.

Filters support station address, broadcast, promiscuous, all multicast and a
64-bit multicast hash. Functional MAC/PHY loopback is implemented. IRQ classes
use vectors 40h (RX), 44h (TX), 48h (system); ISTAT is sticky/W1C and IEN masks lines.

The Clause-22 PHY defaults to address 0, IDs 0022h/561Bh. It supports management
reads/writes, BMCR reset, powerdown/isolation, backend link status and MGTDONE.
`phy-addr` accepts 0–31; the vendor/FreeRTOS board launch uses address 31.

The starters read speed and duplex from active physical members of the host
bridge at startup. With several physical members, they use the lowest speed
and full duplex only if all members report full duplex. TAP interfaces are
ignored. Speeds above 100 Mbps are capped at the F91 PHY's 100 Mbps limit;
unavailable host information falls back to 100 Mbps/full duplex.
Direct QEMU launches can set `-global ez80f91-emac.link-speed=10` (or `100`)
and `-global ez80f91-emac.full-duplex=off` (or `on`).
The link partner advertisement and Am79C874 diagnostic register 18 report
the resulting mode, including guest-forced BMCR modes. With autonegotiation
enabled, the guest advertisement must include the configured partner mode.
PHY and guest reset preserve the configured host mode. Restart the emulator
to read changed host settings; these values do not throttle packet throughput.

## Tests and limits

```sh
python3 tests/test_emac.py build/ez80/qemu-system-ez80
python3 tests/test_host_link.py
```

Tests exercise real socket frames, descriptors/FCS, padding/CRC rejection,
filters, TX/RX wrapping, overflow recovery, invalid pointers, RAM relocation,
PHY link changes, all three IM2 IRQ classes and periodic TX polling.
The full FreeRTOS test additionally verifies DHCP, ARP, ICMP and TCP console data.

This is a functional packet model: no PHY waveforms, physical 10/100-Mbit timing,
collisions/backoff, pause/jam flow control, FIFO test mode, proprietary headers
or complete 802.3 error classification. Backend corrupt frames do not become
simulated PHY errors. VLAN tags are passed through and marked on RX; special
VLAN padding is absent.

MII transactions complete synchronously. SCAN refreshes PRSD on read; SCINC,
timed scanning, busy timing and link-latch-low are not modeled. Vendor PHY
functions/full autonegotiation and device migration/snapshots remain incomplete.
