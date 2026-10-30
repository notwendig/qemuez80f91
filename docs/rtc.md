# F91 RTC and SNTP

Ports E0h–EDh expose seconds, minutes, hours, weekday, day, month, year, century
and alarm/control registers. Calendar counters support binary and BCD modes.
RTC_UNLOCK freezes counters and allows writes; locked counter writes are ignored.
Month lengths, leap years and year transitions are implemented. System reset
preserves calendar values.

At process startup QEMU's RTC base initializes the calendar. The launcher uses
`-rtc base=utc,clock=host`: host UTC matches SNTP. Weekdays use ISO numbering
(Monday=1, Sunday=7). `-rtc` selects base/time source independently of CPU speed.
Guest-set time has no separate battery file across process restarts.
Alarm registers can be read/written, but comparison, alarm IRQ and sleep wakeup
are not implemented.

```sh
python3 tests/test_rtc.py build/ez80/qemu-system-ez80
```

The ZTP demonstration accesses these registers through its original RTC driver.
Its shell command expects a numeric server address:

```text
SNTPClient 192.168.77.1
```

On receive overflow the MAC writes a final RxOVR descriptor, allowing the
original Zilog driver to detect the condition and resume reception.
See [EMAC](emac.md).
