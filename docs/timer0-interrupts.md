# Timer0, Timer1 und F91-Vektorpfad

## Nachgewiesen

Die unveränderte `EZ80F910300ZCOG/src/vectors24.asm` aus
`notwendig/FreeRTOS-eZ80f91` läuft im Emulator. Geprüfter Commit:
`cc64b750e7a5c6dfd19dd8eb3a644a9243ce10a9`.
Quell-SHA-256: `994be83e3f99fe062e8c05de8089f1badcc43e6112527d1dbc9e39a40f943b2b`.

Die Probe durchläuft den ursprünglichen Reset-/Trap-Start, die vollständige
`__init_default_vectors`-Routine und `_set_vector`. Timer0 ruft danach den
generierten Vektortrampolin und den originalen `irq`-Sicherungswrapper auf.
Der neue Testhandler liest TMR0_IIR, zählt und sendet `T`. Nach drei Ticks
stoppt die Hauptschleife den Timer und hält an. Erwartete Ausgabe: `TTT`.
BC, DE, HL, IX, IY und SPL behalten dabei ihre vorbereiteten Werte.
Systemreset und derselbe Lauf erneut sind ebenfalls getestet.

Die kleinen Hooks sind Testcode. Das Symbol `switch` ist hier ein unbenutzter
Stub zum Linken der Originaldatei. Diese Vektorprobe selbst enthält keinen Kernel. Ein tatsächlicher
Taskwechsel ist mit den separaten [Kernelproben](freertos-tasks.md) geprüft;
auch der [Original-Boardstart mit PLL](board-startup.md) ist inzwischen im
RAM-Debugprofil nachgewiesen. Andere Boardgeräte bleiben unvollständig.

## Implementierung

- Separater F91-Interruptcontroller mit 48 Eingängen, zwei Prioritätsstufen,
  INT_P0–INT_P5 an 10–15 und fester Reihenfolge innerhalb einer Stufe.
  Die unbenutzten Quellen 9 und 10 werden ausgeblendet. Timer0 ist
  als Quelle 5 / Vektor 054 angeschlossen, Timer1 als Quelle 6 / Vektor 058; hinzugekommen ist PLL als Quelle 3 /
  Vektor 04C. Weitere Geräte erzeugen noch keine IRQs.
- CPU nimmt maskierbare F91-Vektorinterrupts an. ADL: Tabelle ab
  `(I & FFFE) << 8`, Z80 ohne MADL: MBASE plus `(I & FE) << 8`.
  Das untere I-Bit wird durch den 9-Bit-Vektor ersetzt, wie PS0192 es fordert.
- IEF1 und IEF2 werden beim Eintritt gelöscht. EI erlaubt eine Annahme erst
  nach Abschluss des folgenden Befehls. HALT wird bei annehmbarem IRQ verlassen.
- Ohne MADL werden Rücksprungadressen auf SPS oder SPL gespeichert.
  Mit MADL erfolgt der Eintritt nach ADL auf SPL, mit dem F91-Interruptmarker
  **0/1**. RETI.L stellt Modus und PC wieder her. Gemischte CALL-/RET-Marker
  **2/3** bleiben davon getrennt. RETI setzt IEF nicht selbst; die ISR führt EI aus.
- Timer0: Register 60–64; Timer1: Register 65–69. Beide unterstützen Single-Pass/Continuous, Reload, Teiler 4/16/64/256,
  EOC-Status, Interruptfreigabe und Read-to-clear von IIR.
- Daten-Low lesen latcht Daten-High. RR-Schreibzugriffe verändern den Reloadwert;
  RLD übernimmt ihn in den Zähler. Reload null bedeutet 65536 Zählschritte.
- CLK_PPD2 (DC), Bit 0 friert Timer0 ein, Bit 1 unabhängig davon Timer1.
  Freigabe setzt den jeweiligen Restzähler fort. Timer2/3 fehlen weiterhin.
- Zeitbasis ist QEMUs virtuelle Uhr mit standardmäßig 50 MHz.
  Inzwischen liefert das [Taktmodell](board-startup.md) den Timer-Eingangstakt
  und übernimmt auch laufende Wechsel zwischen Oszillator, PLL und RTC-Takt. Reload 3125 und Teiler 16
  ergeben 1 ms, entsprechend `port.c`. Verpasste Perioden werden mit einem
  gesetzten EOC-Bit zusammengefasst; es entsteht keine künstliche IRQ-Warteschlange.

Quellen: PS019217-1222 S. 48, 57–62 und 123–138 sowie UM007715-0415
S. 36 und 297–299. Die F91-spezifischen Marker 0/1 haben Vorrang gegenüber
der generischen CPU-Darstellung. RETN ist inzwischen implementiert; NMI-Quellen bleiben offen.
Neue Block-I/O-/SLP-IRQ-Proben: [Erweiterte Opcodes](extended-opcodes.md).
IM wird gespeichert; F91-Maskierinterrupts verwenden grundsätzlich den
Vektorpfad. RTC-/externe Timerquellen und elektrische Timer-Ausgänge fehlen.
QEMUs globales Anhalten friert die virtuelle Uhr ein; ein gesondertes
BRK_STOP-Debuggermodell und zyklusgenaue CPU-Laufzeiten fehlen weiterhin.

## Start und Neubau

```sh
build/ez80/qemu-system-ez80 -M ez80f91-freertos,ram-boot=on -kernel examples/timer0_vectors/probe.bin -icount shift=0 -display none -monitor none -serial mon:stdio
```

Ausgabe `TTT`, anschließend HALT; Ctrl-A X beendet QEMU. Die Raw-Datei ist
438529 Bytes groß, weil ein initialisiertes RAM-Byte in der Linkerdatei bei
06B100 liegt und die Zwischenräume mit FF aufgefüllt werden. Tatsächlich
belegt der Code nur 1876 Bytes; diese Angaben stammen aus `probe.map`.

```sh
python3 examples/timer0_vectors/build.py --zds /pfad/zu/ZDSII_eZ80Acclaim!_5.3.5 --freertos /pfad/zu/FreeRTOS-eZ80f91 --out build/timer0-vectors
python3 tests/test_freertos_vectors.py build/ez80/qemu-system-ez80 build/timer0-vectors/probe.bin
python3 tests/test_timer_irq.py build/ez80/qemu-system-ez80
```

Der Build wurde mit dem gespeicherten Skript unter Wine wiederholt. Binary,
Map und Hash-/Symbolmetadaten sind unter `examples/timer0_vectors/` gesichert.
Die unveränderte Original-ASM-Datei wird erst beim Neubau aus dem angegebenen
FreeRTOS-Checkout kopiert.

## Tests

- Periodischer 1-kHz-Timer, HALT-Wecken, RETI und RETI.L.
- Z80-zu-ADL-Interrupteintritt und Rückkehr mit F91-Marker 0.
- Ungerades I-Bit ignoriert; 512-Byte-Vektororientierung.
- Bereits anliegender IRQ wird erst nach dem Folgebefehl von EI angenommen.
- Single Pass löscht TIM_EN; EOC bleibt gesetzt und wird beim Lesen gelöscht.
- High-Byte-Latch sowie Clock-Powerdown mit fortgesetztem Restzähler.
- Original-Vektorinitialisierung, echte Handlerinstallation, Trampolin und
  Register-Sicherungswrapper; drei ISR-Aufrufe, Register/Stack und Reset.

Der allgemeine 48-Quellen-Arbiter ist implementiert. Konkurrenz zwischen
PLL und Timer0 ist mit umgeschalteter Priorität getestet; weitere externe
Quellen sind noch nicht als Geräte angeschlossen.

## Weiterführender Nachweis

Der separate [FreeRTOS-Tasktest](freertos-tasks.md) verwendet inzwischen den
echten Kernel und das originale `llport.asm` anstelle des `switch`-Stubs
dieser Vektorprobe.

## LED-Matrix im FreeRTOS-Demo

`LED5x7Tick` verwendet Timer1, Vektor 058h. Ohne diesen Timer bleiben
LED5x7- und TaskLED-Task beim Warten auf den nächsten Scan stehen.
Timer1 nutzt denselben Systemtakt wie Timer0, aber eigene Zähler, Reload-,
Status- und Interruptregister. `tests/test_timer_irq.py` prüft beide
Interruptquellen sowie ihre unabhängige Clock-Abschaltung.

Der SysInfo-Monitor ist separat auf UDP 4060 erreichbar:

```sh
nc -u 192.168.77.26 4060
```

Einmal Enter sendet das erste Datagramm und startet die ANSI-Statusanzeige.
Die LED-Anzeige wird mit `./start.sh --kit` geöffnet.

Die Matrix integriert den Multiplex-Scan über 40 ms Gastzeit. Zwischen
vollständigen Frames bleibt das letzte Zeichen sichtbar, auch wenn die
Emulation langsamer als Echtzeit läuft.
