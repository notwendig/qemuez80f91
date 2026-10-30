# Flash, persistence and UART0

The models implement the information-page and UART interrupt paths required
by the original ZTP TCPUDPDemo. Hardware reference: PS019217-1222 flash/UART chapters.

## Flash controller

Memory-device registers F5h–FFh expose a separate 512-byte information page,
initially FFh and retained across `system_reset`. Access it through FLASH_DATA
(F6h) with INFO_EN in FLASH_PAGE, independently of CPU flash mapping.

Implemented behavior includes NOR byte programming (1→0 only), reads, address
advancement across column/row boundaries, information-page erase and row-program
completion. Erase bits clear automatically. FLASH_IRQ reports DONE/errors and
acknowledges them on read; DONE_IEN/ERR_IEN drive vector 50h. The B6h/49h key
sequence unlocks FLASH_FDIV and FLASH_PROT until either is written.

The 256-KiB main array supports NOR programming through memory or FLASH_DATA,
2-KiB page erase and mass erase. Eight FLASH_PROT bits protect 32 KiB each;
violations set WR_VIO/PG_VIO/MASS_VIO. Successful erase sets DONE for the original
ZDS loader's polling loop. Mass erase includes the information page only with
INFO_EN; page erase with INFO_EN affects only that page.

Erase completes synchronously; real delays and row-program timeouts are not
modeled. The key sequence does not track intervening I/O writes to other devices.
The WP pin is not modeled separately, and the information page has no cross-process
persistence file.

## UART0

FIFO mode has a 16-byte RX buffer, trigger levels 1/4/8/14 and timeout after four
character times, based on SCLK and the baud divisor. A 1.5-stop-bit setting is
approximated as two. Non-FIFO mode holds one received byte.

RX, timeout, overrun/line status, THRE and transmit-complete use IIR/IER and
vector 70h. RX precedes TX. LSR read acknowledges overrun; IIR read acknowledges
the THRE latch. FIFO reset, DLAB, scratch register, pin multiplexing and PPD gating
remain effective. Internal RX/TX loopback is implemented.

TX reaches the character backend immediately: there is no timed TX FIFO or
shift register. Connected streams present CTS/DSR/DCD; modem edges/IRQs,
parity/framing/break errors and multidrop are not implemented. Mid-timeout format
or clock changes are not cycle-accurate.

## Tests

```sh
python3 tests/test_flash_uart.py build/ez80/qemu-system-ez80
```

Guest tests cover programming/reset retention, address wrapping, erase,
row completion, unlock/relock, flash IRQs, UART buffering/loopback/acknowledgment,
timeout/overrun and RX/TX IM2 paths. Original vendor drivers additionally run in
[ZTP TCP/UDP](ztp-tcpudp.md).

## Persistent flash files

At process startup QEMU loads only internal flash (256 KiB). External 1-MiB
flash chips start filled with FFh. After firmware writes a valid enabled CS
memory window, QEMU attaches the file for its actual lower address. Reset alone
does not load an external file. Reactivating the same base preserves contents;
changing the base saves the old file and loads the new one.

Raw files reside in the current working directory:
`ez80f91_<BASEADDR>.<DEBUGPORT>`, uppercase hexadecimal without leading zeros.
Internal flash uses base `0`; without `--dbgport`, the suffix is `.0`.
There are no fixed external file addresses. Orderly exit, SIGINT and SIGTERM
save internal and attached external flash. Duplicate file addresses are rejected.

Missing files and short tails are filled with FFh. Oversized/unreadable files
cause an error. `-bios` overwrites the beginning of loaded internal flash;
without it, execution starts from saved contents. RAM `-kernel` loading remains
available. Information-page storage is separate. SIGKILL/crashes cannot save state.

```sh
python3 tests/test_flash_persistence.py build/ez80/qemu-system-ez80
```

The original ZDS erase wait and RAM programming path are also tested:

```sh
python3 tests/test_internal_flash.py build/ez80/qemu-system-ez80
```
