# Ergänzte eZ80F91-Opcodes

Stand: 28.10.2026. Grundlage: lokales Zilog **UM007715-0415**, insbesondere
Opcode-Maps, Tabellen 106–112, sowie **PS019217-1222** für F91-SLEEP und die
F91-Interruptframes. Die neuen Encodings werden zusätzlich mit dem installierten
ZDS-II-Assembler geprüft. Der Decoder und der Laufzeitpfad am Adressüberlauf
verwenden dieselbe Implementierung.

## Ergänzungen

- DAA, CCF, NEG; RLD/RRD; TST für Register, `(HL)` und Immediate sowie TSTIO.
- IXH/IXL/IYH/IYL: Immediate-/Register-LD, alle acht 8-Bit-ALU-Gruppen sowie
  INC/DEC; zusätzlich INC/DEC `(IX/IY+d)`.
- IN/OUT über BC und über `{A,n}`. Bei `IN A,(n)` bleiben die Flags erhalten;
  bei `IN r,(BC)` werden S/Z/P aktualisiert und Carry erhalten.
- Alle 28 Block-I/O-Encodings: INI/IND/OUTI/OUTD, INIR/INDR/OTIR/OTDR,
  INIM/INDM/OTIM/OTDM samt Wiederholvarianten, INI2/IND2/OUTI2/OUTD2,
  INI2R/IND2R/OTI2R/OTD2R und INIRX/INDRX/OTIRX/OTDRX.
- LD R,A, LD A,R und LD HL,I.
- Alle acht RST-Vektoren einschließlich gemischter SPS/SPL-Frames;
  RETN einschließlich der F91-Marker 0/1 für lange Interrupt-Rückkehr.
- SLP mit CPU-Schlafzustand: maskierbare IRQs wecken die F91-CPU nicht auf;
  Systemreset löscht den Schlafzustand.

Beim Abgleich wurde außerdem ein bestehender Zielfehler korrigiert:
**ED31 lädt IY aus `(HL)`, ED37 lädt IX**. Die Stores ED3E/ED3F waren korrekt.

## Decoder-Abdeckung

Die folgende Zählung betrifft gültige Opcodebytes pro ungesuffixtem
Opcode-Raum, unabhängig von konkreten Operanden. Sie zählt keine Mnemonics
oder sämtliche ADL-/Suffixkombinationen. Die acht Dispatcherbytes im ersten
Opcode-Raum werden dort nicht mitgezählt.

| Opcode-Raum | Vorher | Jetzt | Neu implementiert | Ungültige entfernt |
| --- | ---: | ---: | ---: | ---: |
| Erster Opcode, ohne Dispatcher | 236 | 248 | 12 | 0 |
| ED | 75 | 135 | 60 | 0 |
| DD | 48 | 95 | 48 | 1 |
| FD | 48 | 95 | 48 | 1 |
| CB | 248 | 248 | 0 | 0 |
| DD CB d / FD CB d, jeweils | 31 | 31 | 0 | 0 |

Damit sind **168 weitere Opcode-Encodings** im Decoder zugelassen und mit
Seiteneffekten implementiert. Reservierte ED-Bytes, das undokumentierte SLL
und ungültige Präfixkombinationen bleiben ungültige Instruktionen und
lösen jetzt den Hardware-TRAP an Vektor 0 aus. `test_illegal_traps.py` prüft
die gespeicherte Adresse des illegalen Opcodebytes, ADL/Z80-Stackrahmen und MADL-Marker. Insbesondere sind ED D2/D3/DA/DB keine zusätzlichen RX-Aliasse.
DD76 und FD76 wurden bislang irrtümlich als Speichertransfer zugelassen und
sind nun ebenfalls korrekt ungültig.

`tests/test_opcode_maps.py` vergleicht die vollständigen sieben Opcode-Maps
gegen direkt aus UM0077 übertragene Referenzmengen. Dabei werden in beiden
ADL-Modi gültige **und** reservierte Opcodebytes geprüft. Die Referenzmengen
werden nicht aus den Decoder-Bitmasken berechnet.

## Validierung

```sh
python3 tests/test_opcode_maps.py
python3 tests/test_extended_opcodes.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
python3 tests/test_timer_irq.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
python3 examples/extended_opcodes/build.py
python3 tests/test_zds_ethernet.py
```

`test_extended_opcodes.py` führt 195 ROM-Szenarien und 13 Negativfälle aus.
Darunter sind 60.000 gültige BCD-Operand-/Carry-Kombinationen für
ADD/SUB/ADC/SBC plus DAA. Die Prüfung umfasst Register, Flags, konkrete
RAM-/Portwerte, Carry-/Vorzeichen-/Nullgrenzen, 16-/24-Bit-Zähler,
B=0 als 256 Iterationen, kurze Adressierung über MBASE, Fetch über
64-KiB-/24-Bit-Grenzen und gemischte RST-/RETN-Stackframes. Die Tests laufen
mit `-icount shift=0`, sodass fehlende I/O-Grenzen ebenfalls auffallen.

Der Timer-Test weist einen IRQ **innerhalb** eines INIRX-Transfers nach:
Teilmengenzähler und Rücksprung-PC zeigen auf die noch laufende Wiederholung.
Eine separate Probe prüft SLP trotz anstehendem Timer0-IRQ und anschließenden
Reset. Die 113 Encodings in `examples/extended_opcodes/opcodes.asm` werden
unabhängig vom QEMU-Decoder mit ZDS II assembliert und bytegenau abgeglichen.
Die üblichen CPU-, Speicher-, CAMEL-, FreeRTOS-, Board- und ZDS-Tests bilden
zusätzliche Regressionen.

## Präzisierung und verbleibende Grenzen

- Dies ist kein vollständiger Silizium- oder Zyklusgenauigkeitsnachweis.
  Nicht jede Operand-/Suffixkombination ist exhaustiv geprüft.
- Die M-Block-I/O-Befehle haben teilweise undefinierte S/H/PV/C-Flags. Der
  Emulator erhält diese Bits deterministisch. Definierte Z/N-Bits folgen dem
  eZ80-Handbuch; klassische und erweiterte Befehle erhalten die übrigen
  definierten Flags. Nicht die undokumentierten Z80-Block-I/O-Flagregeln verwenden.
- **LD HL,I:** Die detaillierte Beschreibung auf UM0077 S.195 definiert
  S/Z/H/PV/N und erhält Carry; Zusammenfassung/Opcode-Map nennen dagegen
  unveränderte Flags. Implementiert ist die detaillierte Beschreibung
  (S aus I[15], Z aus dem 16-Bit-I-Wert, PV aus IFF2). Dieser Widerspruch ist
  ohne F91-Hardwarevergleich weiterhin offen. Ein Versuch, den installierten
  Zilog-Simulator als zweite Referenz zu laden, scheiterte an dessen Core-DLL.
- NMI-Quellen und RTC-/WDT-Resetquellen sind weiterhin nicht modelliert.
  RETN kann ausgeführt werden; damit ist noch kein vollständiger NMI-Pfad
  implementiert. Das vorhandene Interruptmodell bleibt auf die bisher geprüften
  F91-Vektor-/IM2-Pfade begrenzt.
- SLP hält die CPU an und sperrt IRQ-Wakeup. Das Abschalten sämtlicher
  Peripherie-/Oszillatortakte und die analogen Wake-/Resetzeiten sind nicht
  modelliert. Ein Debug-Reset funktioniert über den vorhandenen Systemreset.
- Migration bleibt gesperrt. Der private GDB-Registerblock bleibt bei 24 Slots;
  `info registers` zeigt zusätzlich `SLEEP=0/1`.
