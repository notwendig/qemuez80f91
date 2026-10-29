# F91-RTC und SNTP

Die Ports E0h–EDh stellen Sekunden, Minuten, Stunden, Wochentag, Tag,
Monat, Jahr, Jahrhundert sowie Alarm-/Kontrollregister bereit. Die
Kalenderzähler unterstützen binäre und BCD-Darstellung. RTC_UNLOCK hält die
Zähler an und erlaubt Schreibzugriffe; im gesperrten Zustand werden
Zählerschreibzugriffe ignoriert. Monats-, Schaltjahr- und Jahreswechsel sind
implementiert. Ein Systemreset erhält die Kalenderwerte.

Beim Prozessstart wird die Uhr aus QEMUs RTC-Basis initialisiert. Der Starter
setzt explizit `-rtc base=utc,clock=host`: Datum und Uhrzeit stammen vom Host
in UTC, passend zu SNTP. Wochentage starten mit ISO-Zählung (Montag=1 bis
Sonntag=7). `-rtc`
bestimmt Basis und Zeitquelle; damit bleibt die Uhr unabhängig von der
CPU-Instruktionsgeschwindigkeit. Es gibt keine separate Batterie-Datei für
vom Gast gesetzte Uhrzeiten über QEMU-Prozessneustarts hinweg.
Alarmregister sind les-/schreibbar; Alarmvergleich, Alarminterrupt und
Sleep-Wakeup sind noch nicht implementiert.

```sh
python3 tests/test_rtc.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
```

Das ZTP-Demo verwendet diese Register über seinen ursprünglichen RTC-Treiber.
Der Shell-Befehl erwartet eine numerische Serveradresse, beispielsweise:

```text
SNTPClient 192.168.77.1
```

Der MAC erzeugt bei Empfangsüberlauf einen abschließenden RxOVR-Deskriptor.
Damit kann der originale Zilog-Treiber den Überlauf erkennen und den Empfang
wieder freigeben; siehe [MAC-Modell](emac.md).
