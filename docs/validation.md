# Validation records

The FreeRTOS Release profile now places its compressed CP/M disk image in external
AMD flash at `0x100000`, with program code in internal flash. The RAM Debug profile
is retained. The split Flash image passed the isolated cold-boot DHCP, ARP, ICMP
and TCP-console test, including an external-image read at `0x100000`. The disk
image matched all 101,820 compressed bytes and decompressed to 256,256 bytes.
See the firmware [build instructions](../subprojects/FreeRTOS-eZ80f91/BUILD.md#zds-ii-535).

## Library and integration updates: 30 October 2026

The following checks were executed during the library upgrades; this is not a
new run of every test in the earlier release table.

- Kernel V11.3.2: preemption, blocking, 24-bit tick rollover and both board/PLL
  variants passed, including reset.
- The CAMEL direct-source build reproduced the saved binary; all 89 UART cases
  passed before and after reset.
- Full ZDS II 5.3.5 firmware compiled and linked with Plus-TCP V4.4.2 and
  uzlib `6d60d65`. Release was subsequently repaired and rebuilt with zero
  warnings/errors using the same RAM profile; its image passed the isolated
  DHCP/ARP/ICMP/TCP-console test.
- Isolated Ethernet test passed DHCP, ARP, ICMP Echo and TCP-console data.
  The updated test also verifies correct full-width IPv4 diagnostics.
- CP/M disk decompression passed CRC, truncation, size and output-bound checks.
- uzlib upstream corpus, malformed inputs and a compressor/Python-gzip round trip passed.
- Dependency setup passed on fresh local clones and on repeated invocation.
- The three ZDS possibly-uninitialized warnings were corrected; affected sources
  recompiled without those warnings and the network regression passed.

Physical hardware and live CP/M/button sessions were not revalidated by this
upgrade test set.

## Final pre-push checks: 30 October 2026

All 28 local scripts in the table below passed again against the current
`build/ez80/qemu-system-ez80`. The initial run exposed shared working-directory
flash contamination; the VM helper now uses an isolated directory by default,
and the internal-flash persistence test explicitly selects its temporary path.
The complete firmware network test also passed with correct IPv4 diagnostics.
Fresh-clone/repeated library setup, fixture hashes and Python/shell syntax passed.
All 35 maintained Markdown documents use English; 153 local links and shell
syntax in 74 documentation examples were checked. Logs are in `build/prepush/`.

## Historical release run: 29 October 2026

The earlier release run used the then-current QEMU patch and local executable:

- 28/28 local scripts and 2/2 original-DLL SDK integration tests passed.
- Forth: 237/237 entries reached, 201 result checks; another 89 cases before/after reset.
- 131 local Markdown links in 35 documents were checked at that time.
- Python/shell syntax, fixture hashes and reverse QEMU-patch application passed.
- Library setup reproduced the dependency state used by that earlier release.

### Local results

| Script | Result | Duration |
| --- | --- | ---: |
| `test_board_startup.py` | passed | 4.37 s |
| `test_camelf91.py` | passed | 8.13 s |
| `test_camelf91_kit.py` | passed | 2.57 s |
| `test_camelf91_words.py` | passed | 62.90 s |
| `test_chip_selects.py` | passed | 0.97 s |
| `test_cpu_uart.py` | passed | 0.87 s |
| `test_cstartup_ops.py` | passed | 2.57 s |
| `test_dbgport.py` | passed | 0.57 s |
| `test_emac.py` | passed | 0.62 s |
| `test_extended_opcodes.py` | passed | 13.24 s |
| `test_flash_persistence.py` | passed | 0.42 s |
| `test_flash_uart.py` | passed | 0.31 s |
| `test_freertos_blocking.py` | passed | 3.62 s |
| `test_freertos_tasks.py` | passed | 1.92 s |
| `test_freertos_unzip.py` | passed | 0.67 s |
| `test_freertos_vectors.py` | passed | 0.16 s |
| `test_illegal_traps.py` | passed | 2.22 s |
| `test_internal_flash.py` | passed | 0.16 s |
| `test_kit.py` | passed | 0.41 s |
| `test_kit_buttons.py` | passed | 0.47 s |
| `test_kit_frames.py` | passed | 6.13 s |
| `test_memory.py` | passed | 0.21 s |
| `test_opcode_maps.py` | passed | 0.87 s |
| `test_pll.py` | passed | 1.32 s |
| `test_rtc.py` | passed | 6.48 s |
| `test_smoke.py` | passed | 0.21 s |
| `test_timer_irq.py` | passed | 0.92 s |
| `test_zds_cstartup.py` | passed | 0.21 s |

### Original vendor DLL

`test_zds_ethernet.py --native` checked initialization, views, RAM, stepping,
breakpoints, run/stop and independent QMP state. `test_zds_flash.py` checked
internal and external AMD erase/program/readback through the same original DLL.
Both used isolated QEMU instances and temporary flash files.

### Reproduction and limits

Historical QEMU SHA-256:
`29ea03fb205c3d8df244ffcffc2ae8aeaa2330fa1df121cd0028bdfc867fea9b`.
The local path was `/tmp/qemuez80f91-build-baseline/qemu-system-ez80`;
other machines should follow [Getting started](getting-started.md).

Release logs are generated under `build/validation/`; Forth coverage is under
`build/camelf91-words/report.json`. Generated reports are not tracked portable
source artifacts. Real-network DHCP/UDP/TCP, live CP/M/buttons, GUI actions and
physical hardware were not rerun as part of that historical release batch.
Their separate requirements are listed in [Testing](testing.md).
