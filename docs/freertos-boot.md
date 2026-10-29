# FreeRTOS-Projekt: erster echter C-Startup

## Nachgewiesener Stand

Erweitert durch [Timer0 und den Original-Vektorpfad](timer0-interrupts.md).

Der Emulator führt den **unveränderten `cstartup.asm` aus dem FreeRTOS-Projekt**
und ein mit dem originalen Zilog-C-Compiler übersetztes Test-`main()` aus.
Das Testprogramm erreicht HALT in `main`, berechnet `0x123456` und sendet
`C` über UART0. Systemreset und erneute Ausführung liefern dasselbe Ergebnis.

Die Probe ist 253 Bytes groß. Sie ist ein bewusst reduzierter Startpfad:
die Reset-/Vorbereitungsroutine und das Test-main sind neu; der C-Startup
und der benötigte `__frameset`-Helfer stammen aus dem Projekt bzw. der
lokalen ZDS-Laufzeitbibliothek. Der FreeRTOS-Kernel und das originale Demo-main
sind nicht Teil dieses Binaries. Zwei schedulende Tasks sind inzwischen mit
der separaten [Präemptionsprobe](freertos-tasks.md) nachgewiesen;
[weitere Kernelproben](freertos-blocking.md) prüfen Yield, Delay und Ticküberlauf.

## Geprüfte Grundlage

- Repository: https://github.com/notwendig/FreeRTOS-eZ80f91
- Geprüfter Commit: `cc64b750e7a5c6dfd19dd8eb3a644a9243ce10a9`.
- Originalquelle: `EZ80F910300ZCOG/src/cstartup.asm`.
- Deren SHA-256: `697803471cc7d34f33a011db7fee2f12d482872475189551ae5120210226ff46`.
- Speicherprofil: `eZ80F91_99C0879_RAM.ztgt` und `bin/EZ80F910300ZCOGd.map`.
- Tatsächlich verwendete Werkzeuge: ZDS II eZ80Acclaim! 5.3.5,
  C-Compiler 3.4, Assembler 4.3, Linker 6.25, unter Wine.

Die veröffentlichte Demo-Map ist ein RAMONLY/CPM22-Debugbuild: Code ab 0,
initialisierte Daten ab 06B000, zusätzlicher RAM-Bereich B80000–B8FFFF,
Stack bei B90000. Das Flash-Target `.ztgt` hat ein anderes Speicherprofil
und wird mit dieser Maschine noch nicht vollständig nachgebildet.

## Neue Maschine und Speichersteuerung

`ez80f91-freertos` ist ein aus den genannten Dateien abgeleitetes
RAM-Entwicklungsprofil; kein vollständiges elektrisches Modell des Boards.

| Bereich | Speicher / Verdrahtung im Profil |
| --- | --- |
| 000000–07FFFF | 512 KiB externes SRAM an CS1 |
| B80000–BFFFFF | 512 KiB externes SRAM an CS2 |
| internes Flash | 256 KiB, über FLASH_ADDR_U verschiebbar |
| internes allgemeines RAM | 8 KiB, Offset E000 in RAM_ADDR_U |
| internes EMAC-RAM | 8 KiB, Offset C000 in RAM_ADDR_U |

Die äußeren SRAM-Bereiche bleiben an ihren Boardadressen. Die CS-Register
bestimmen den sichtbaren Ausschnitt; ein außerhalb der SRAM-Verdrahtung
liegender CS-Bereich erzeugt keinen zusätzlichen Speicher. SRAM-Inhalte
bleiben bei Decoderänderungen erhalten.

Unterstützt sind CS0–CS3 LBR/UBR/CTL (A8–B3), BMC (F0–F3), RAM_CTL (B4),
RAM_ADDR_U (B5), FLASH_ADDR_U (F7) und FLASH_CTRL (F8). Reservierte Bits
werden maskiert. Priorität: internes RAM vor internem Flash vor externem
SRAM. CS0/CS3 haben in diesem Profil keinen angeschlossenen externen Baustein;
externe Flashprogrammierung und I/O-Chipselect-Geräte fehlen.
Busmodi/Wait-State-Felder werden gespeichert, ihre Laufzeiten nicht simuliert.

Ohne Zusatzoption gelten die Hardware-Resetwerte. Mit **`ram-boot=on`**
setzt die Maschine bei Reset ausdrücklich debuggerähnliche Werte aus dem
RAM-Target: CS1=00/07/28, CS2=80/BF/28, internes Flash deaktiviert (60),
RAM aktiviert bei FF. Das ist eine Debugger-Vorbereitung, kein behaupteter
Silizium-Resetzustand. Sie wird für `-kernel` verwendet; `-bios` bleibt der
Bootweg für internes Flash. Raw-Kernel bis 512 KiB werden akzeptiert.

## Probe starten

```sh
build/ez80/qemu-system-ez80 -M ez80f91-freertos,ram-boot=on -kernel examples/zds_cstartup/probe.bin -display none -monitor none -serial mon:stdio
```

Erwartete UART-Ausgabe: `C`, anschließend HALT. Ctrl-A X beendet QEMU.
Mit dem Build dieser Sitzung lautet der Programmpfad
`/tmp/qemuez80f91-build-baseline/qemu-system-ez80`.

Die Quellen, das Binary, die Linker-Map und die Herkunftsdaten liegen unter
`examples/zds_cstartup/`. Für einen Neubau werden die vorhandene ZDS-Installation,
Wine und ein Checkout des oben genannten FreeRTOS-Commits benötigt:

```sh
python3 examples/zds_cstartup/build.py --zds /pfad/zu/ZDSII_eZ80Acclaim!_5.3.5 --freertos /pfad/zu/FreeRTOS-eZ80f91 --out build/zds-probe
python3 tests/test_zds_cstartup.py build/ez80/qemu-system-ez80 build/zds-probe/probe.bin
```

Das Buildskript kopiert den Original-Startup unverändert in den Buildordner,
protokolliert die Werkzeugaufrufe, erzeugt Intel HEX und konvertiert es mit
Prüfsummenprüfung in ein Raw-Binary. `probe.json` hält Quell- und Binary-Hash,
Commit und die vom Linker ermittelten Symboladressen fest.

## Neue CPU-Befehle für diesen Pfad

Ergänzt wurden ADD HL/IX/IY,rr/SP, ADC/SBC HL,rr/SP, 8-Bit-ALU mit
Registeroperanden, INC/DEC r, EX (SP),HL/IX/IY, EXX und EX AF,AF'.
Dazu kommen LD rr,(nn)/(IX+d)/(IY+d), die entsprechenden Stores,
indizierte Bytezugriffe, LEA, LDI/LDIR sowie LD A,I, LD I,A und LD I,HL.
IM und EI sind dekodiert; Interruptannahme und EI-Verzögerung sind inzwischen
implementiert, siehe [Timer/Vektoren](timer0-interrupts.md). LD HL,I bleibt wegen des Dokumentwiderspruchs offen.

LDIR kopiert pro Ausführung einen Byte-Schritt und gibt bei Wiederholung
an QEMU zurück. Dadurch bleiben lange Kopien unterbrechbar, statt in einer
unbegrenzten C-Schleife zu laufen. 24-Bit-Lasten und Stores bleiben bytegenau.

## Durchgeführte Prüfung

- Speicher verschieben, aktivieren/deaktivieren, Prioritäten und reservierte Bits.
- Externe SRAM-Bereiche, CS2 deaktivieren/reaktivieren und Sichtfenster verkleinern.
- Kerneldatei größer als 256 KiB im RAM-Profil.
- 24-Bit-Carry, Borrow, Half-Carry und Overflow.
- Negative Indexdisplacements, 3-Byte-Transfers mit Guardbyte, Stackaustausch.
- LEA mit beiden Cross-Index-Formen und Schattenregistertausch.
- LDIR-Länge, Zielbytes und Endregister.
- Reproduzierbarer ZDS-Build ohne Compiler-/Assembler-Zielwarnung.
- Original-C-Startup: absichtlich verschmutztes BSS wird gelöscht;
  DATA und berechnetes Ergebnis sind 123456; UART C; gleicher Lauf nach Reset.

Die bisherigen CPU-/UART-Tests bleiben Teil der Regression.

## Nächste echte FreeRTOS-Hürde

Original-Vektorinitialisierung, Handlerinstallation, IRQ-Sicherungswrapper,
Timer0 und RETI.L sind inzwischen geprüft. Es fehlen der Nachweis zweier
echter FreeRTOS-Tasks mit Kernel-Scheduler sowie Teile des vollständigen
init_params_f91-/PLL-Starts. Details und Fortsetzung: [Pausenstand](PAUSE.md).
