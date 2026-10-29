# Originaler F91-Boardstart und PLL

## Nachweis

`init_params_f91.asm` aus dem Originalprojekt läuft unverändert vom
Reset-/Trap-Einstieg in `vectors24.asm` bis zum echten FreeRTOS-Scheduler.
Die Probe verwendet außerdem die unveränderten `cstartup.asm`, `llport.asm`
und den ZDS-Baustein `zsldevinitdummy.obj` für die vorgesehenen
`__open_periphdevice`-/`__close_periphdevice`-Hooks.

Der Startpfad führt die Interrupt-Deaktivierungszugriffe, CS0–CS3- und
Buskonfiguration, interne Speicherbelegung, Stacksetzung, Vektorinitialisierung,
Taktinitialisierung und C-Startup aus. Erst in C-main werden UART0-Pins und
8N1 gesetzt und die beiden echten Tasks angelegt. Beide Varianten geben
`BABABABA!` aus und halten nach sieben Timer-Ticks an.

Die Speicher- und Taktparameter werden beim Build aus der veröffentlichten
`bin/EZ80F910300ZCOGd.map` des Originalprojekts gelesen. Der Test prüft die
Speicher-/PLL-Register beim Eintritt in C-main und den Bootstack nahe B90000.
BSS und DATA werden nach erfolgreicher Initialisierung absichtlich verändert;
nach Systemreset muss der Original-C-Startup sie wieder herstellen. Danach
werden erneut UART-Ausgabe, Taskzähler, TCB-Stackpointer, Schutzwerte und
sieben Scheduler-Ticks geprüft.

| Variante | Oszillator | Startquelle | Systemtakt nach Init |
| --- | ---: | --- | ---: |
| `board` | 50 MHz | Oszillator, Originalparameter | 50 MHz |
| `pll` | 10 MHz | PLL, Multiplikator 5 | 50 MHz |

Der unveränderte Originalparameter `_SYS_CLK_SRC=0` verwendet keine PLL.
Die zweite Variante ändert ausschließlich die gelinkten Taktparameter
`_OSC_FREQ`, `_SYS_CLK_SRC` und `_OSC_FREQ_MULT`, damit auch die bereits
im Original-ASM enthaltene PLL-Initialisierung durchlaufen wird.

## Taktmodell

Ein neues F91-Taktgerät stellt PLL_DIV_L/H und PLL_CTL0/1 an 5C–5F bereit.
Sein QEMU-Clock-Ausgang ist mit Timer0 verbunden.

- Reset: PLL aus, Oszillator als Taktquelle; standardmäßig 50 MHz.
- `-M ...,osc-frequency=10000000` setzt den externen Oszillator auf 10 MHz.
  Unterstützter Maschinenparameterbereich: 1 bis 50000000 Hz.
- Divider: 11 Bit, Low vormerken und erst bei High-Schreibzugriff übernehmen;
  Werte unter zwei werden als zwei behandelt. Lesen liefert null.
- Divider sowie Charge-Pump-/Lock-Kriterien lassen sich nur bei ausgeschalteter
  PLL programmieren. Reservierte Bits bleiben null.
- Die PLL wird erst nach einer virtuellen Wartezeit gelockt. Das Modell
  akzeptiert PLL-Eingänge von 1–10 MHz und Ausgangstakte bis 50 MHz.
- Eine ausgeschaltete oder ungelockte PLL kann nicht als Systemquelle gewählt
  werden. Eine als Systemquelle gewählte PLL lässt sich nicht abschalten.
  Die reservierte MUX-Auswahl 3 erhält die vorherige Quelle.
- Lock-/Unlock-Ereignisse bleiben bis zum Lesen von PLL_CTL1 gesetzt.
  Die zugehörigen Freigabebits steuern den IRQ an Quelle 3 / Vektor 04C.
- Die Auswahl des RTC-Takts liefert einen idealen 32768-Hz-Takt.
  Das RTC-Gerät selbst ist damit nicht implementiert.
- Timer0 übernimmt Taktänderungen auch im laufenden Betrieb. Der Restzähler
  bleibt erhalten; die verbleibende Zeit wird mit dem neuen Takt geplant.

PLL-Lock erfolgt funktional nach festen 100 µs virtueller Zeit. Das ist eine
Emulationsentscheidung, kein behaupteter elektrischer Lock-Zeitwert.
Charge Pump, Lock-Sensitivität und Jitter werden nicht analog simuliert.
Timerzählung rundet auf ganze Ticks/Nanosekunden. Die CPU-Ausführungszeit
bleibt durch QEMUs icount bestimmt; ein taktzyklusgenauer CPU-Kern entsteht
hierdurch nicht. UART0 hat weiterhin kein Baudtiming.

Hardwaregrundlage: PS019217-1222 S. 25–26, 57–58 und 265–273,
insbesondere Tabellen 152–155. Der benötigte `SET 0,A` ist zusammen mit
unindizierten BIT/RES/SET für Register und `(HL)` einschließlich kurzer/langer
Speicheradressierung ergänzt. Indizierte CB-Befehle und CB-Rotationen sind inzwischen für den
[CamelForth-Test](camelf91.md) ergänzt; die CPU-Regression prüft die dokumentierten Flags und Präfixe.

## Grenzen des Startnachweises

Die Probe startet im expliziten RAM-Debugprofil `ram-boot=on`, mit dem bereits
getesteten externen SRAM und deaktiviertem internem Flash. Ein Kaltstart aus
Flash und das vollständige Original-Demoprogramm sind nicht abgedeckt.

Die Abschaltzugriffe auf noch nicht modellierte Geräte wie I2C, SPI, EMAC,
RTC, UART1, Timer1–3 und GPIO A–C werden ausgeführt, erhalten dadurch aber
keine Gerätefunktion. Der Original-ZDS-Peripheriehook ist ein Dummy; die für
den Test benötigte UART-Konfiguration erfolgt in main. Der nachgewiesene
Umfang ist der vollständige Original-Initialisierungspfad im RAM-Profil,
Taktsteuerung und anschließender Kernelbetrieb.

## Start und Tests

Gesicherte Quellen, Images, Maps und Hash-/Symbolmetadaten liegen in
`examples/freertos_tasks/board/`:

- `probe.bin/json/map`: Originalparameter mit 50-MHz-Oszillator.
- `pll.bin/json/map`: 10-MHz-Oszillator und PLL-Multiplikator 5.

Beide Images sind 444869 Bytes groß; die ROM-Belegung beträgt 12804 Bytes.
Die Linkerbereiche entsprechen der veröffentlichten Map:
ROM 000000–06AFFF; RAM 06B000–07FFFF und B80000–B8FFFF; Stack B90000.

```sh
build/ez80/qemu-system-ez80 -M ez80f91-freertos,ram-boot=on,osc-frequency=10000000 -kernel examples/freertos_tasks/board/pll.bin -icount shift=0 -display none -monitor none -serial mon:stdio
python3 tests/test_board_startup.py build/ez80/qemu-system-ez80
python3 tests/test_pll.py build/ez80/qemu-system-ez80
```

Der Boardtest führt standardmäßig beide Varianten jeweils vor und nach Reset
aus. Ein einzelnes Image ist als zweites Argument möglich. Ctrl-A X beendet
den interaktiven Emulator nach HALT.

Der PLL-Test prüft Reset-/Registerwerte, Schreibschutz, Divider-Latch und
Mindestwert, Lock-/Unlock-Lesen, Abbruch einer anstehenden Lock-Phase,
ungültige PLL-Eingänge sowie die Wirkung der drei Taktquellen auf einen
laufenden Timer. Zwei gleichzeitig anliegende IRQs werden einmal mit
Standardpriorität (PLL vor Timer) und einmal mit hoher Timerpriorität in
umgekehrter Reihenfolge bedient. Auch diese Fälle werden nach Reset wiederholt.

## Neubau

```sh
python3 examples/freertos_tasks/build.py --scenario board --zds /pfad/zu/ZDSII_eZ80Acclaim!_5.3.5 --freertos /pfad/zu/FreeRTOS-eZ80f91 --kernel /pfad/zu/FreeRTOS-Kernel --out build/freertos-board
python3 examples/freertos_tasks/build.py --scenario pll --zds /pfad/zu/ZDSII_eZ80Acclaim!_5.3.5 --freertos /pfad/zu/FreeRTOS-eZ80f91 --kernel /pfad/zu/FreeRTOS-Kernel --out build/freertos-pll
```

Die Kernelbasis bleibt V10.6.1 mit Originalprojekt-Patch. Die bisherigen
Szenarien `preempt`, `blocking` und `wrap` sind weiterhin verfügbar.
Die Metadaten enthalten zusätzlich den Hash von `init_params_f91.asm` und
sämtliche aus der Original-Map übernommenen Initialisierungsparameter.

## Validierung dieses Standes

Alle elf Integrationstestskripte bestanden. Unabhängige Neubauten
reproduzieren beide Board-Binaries und ihre Metadaten exakt. Der Gesamtpatch
lässt sich auf die unveränderten QEMU-Basisdateien anwenden und reproduziert
den Arbeitsstand. QEMU-Checkpatch meldet null Fehler; es bleibt der allgemeine
MAINTAINERS-Hinweis für neue Dateien.
