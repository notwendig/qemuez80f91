# FreeRTOS: Yield, Delay und Ticküberlauf

## Nachgewiesenes Verhalten

Die Probe erweitert den echten FreeRTOS-V10.6.1-Kerneltest um freiwillige
Taskwechsel, blockierende Aufrufe und die Idle-Task. Kernel, Projektpatch,
Original-Vektorwrapper und `llport.asm` entsprechen der
[Präemptionsprobe](freertos-tasks.md). Weitere CPU- oder Geräteänderungen
waren für diesen Meilenstein nicht nötig.

Zwei gleich priorisierte Tasks durchlaufen zunächst eine Phase mit gestopptem
Timer0. Task B tritt zweimal, Task A einmal in einen kritischen Abschnitt ein.
Beide wechseln freiwillig mit `taskYIELD()` zum anderen Task. Beim Fortsetzen
prüfen sie ihre jeweilige Verschachtelung, den gesperrten Interruptstatus und
einen lokalen Stackwert. Nach dem Verlassen der kritischen Abschnitte sind
Interrupts wieder freigegeben. Die Ausgabe `BAba` und unveränderte Tickwerte
belegen die Reihenfolge ohne Timer-Präemption.

Anschließend startet B Timer0 und gibt `D` aus. B schläft dreimal je zwei
Ticks, A zunächst fünf und danach zehn Ticks mit `vTaskDelay`. Beide verlassen
damit die Ready-Liste; zwischen den Weckzeitpunkten läuft die niedriger
priorisierte Idle-Task. Die Idle-Hook merkt die tatsächlich beobachteten
Ticks. Nach sechs Ticks beendet B die Probe mit DI und HALT.

| Ereignis | Ausgabe | Tick relativ zum Timerstart |
| --- | --- | ---: |
| Freiwillige Wechsel und kritische Abschnitte | `BAba` | 0 |
| Timerstart | `D` | 0 |
| B wacht erstmals auf | `2` | 2 |
| B wacht erneut auf | `4` | 4 |
| A wacht auf | `5` | 5 |
| B wacht zum dritten Mal auf | `6` | 6 |
| Erfolgreicher Abschluss | `!` | 6 |

Die vollständige Ausgabe lautet `BAbaD2456!`. Der Integrationstest prüft
zusätzlich die Tickwerte jedes Ereignisses, die Durchlaufzähler A=2/B=4,
eine laufende Idle-Task in den sechs Warteintervallen, gespeicherte und aktive
Stackpointer, Schutzwerte aller drei Stacks, kritischen Zähler null und den
Endzustand mit gesperrten Interrupts. Danach wird QEMU zurückgesetzt und der
gesamte Ablauf erneut geprüft.

## 24-Bit-Ticküberlauf

Die zweite Variante setzt `configINITIAL_TICK_COUNT` auf `FFFFFC`.
Der Originalport definiert `TickType_t` als `uint24_t`; der Kernelzähler ist
entsprechend 24 Bit breit. Die Ereignisse liegen damit bei:

| Relativer Tick | Kernel-Tick |
| ---: | --- |
| 0 | `FFFFFC` |
| 2 | `FFFFFE` |
| 4 | `000000` |
| 5 | `000001` |
| 6 | `000002` |

Damit werden auch das Umschalten der verzögerten Tasklisten beim Überlauf
und das Wecken über die Überlaufgrenze hinweg ausgeführt. Der unabhängige
Uptime-Zähler aus `llport.asm` beginnt weiterhin bei null und muss am Ende
in beiden Varianten sechs melden. Die konfigurierte Taktquelle bleibt
Timer0 mit 1 kHz bei 50 MHz Systemtakt.

## Gesicherte Proben und Start

Unter `examples/freertos_tasks/blocking/` liegen:

- `main.c`, `boot.asm` und `FreeRTOSConfig.h`: die Quellen der neuen Probe.
- `probe.bin`, `probe.json`, `probe.map`: Lauf ab Tick null.
- `wrap.bin`, `wrap.json`, `wrap.map`: Lauf über den Ticküberlauf.

Beide Raw-Images sind jeweils 445001 Bytes groß. Die Linkeradressen und die
unbenutzte CP/M-Reservierung aus dem originalen `llport.asm` werden wie bei
der Präemptionsprobe beibehalten. ROM-Belegung: 13478 Bytes normal,
13502 Bytes mit Ticküberlauf. Metadaten enthalten Kernelcommit,
Originalpatch-Hash, Quellhashes, Symboladressen und Binary-Hash.

```sh
build/ez80/qemu-system-ez80 -M ez80f91-freertos,ram-boot=on -kernel examples/freertos_tasks/blocking/probe.bin -icount shift=0 -display none -monitor none -serial mon:stdio
python3 tests/test_freertos_blocking.py build/ez80/qemu-system-ez80
```

Der Test führt standardmäßig beide Varianten samt Reset aus.
Ein einzelnes Image kann als zweites Argument angegeben werden.
Für den Überlauflauf beim interaktiven Start `probe.bin` durch `wrap.bin`
ersetzen. Ctrl-A X beendet QEMU nach dem HALT.

## Reproduzierbarer Neubau

Benötigt werden die bereits dokumentierten ZDS- und Originalprojektquellen
sowie ein FreeRTOS-Kernel-Checkout auf Tag V10.6.1.

```sh
python3 examples/freertos_tasks/build.py --scenario blocking --zds /pfad/zu/ZDSII_eZ80Acclaim!_5.3.5 --freertos /pfad/zu/FreeRTOS-eZ80f91 --kernel /pfad/zu/FreeRTOS-Kernel --out build/freertos-blocking
python3 examples/freertos_tasks/build.py --scenario wrap --zds /pfad/zu/ZDSII_eZ80Acclaim!_5.3.5 --freertos /pfad/zu/FreeRTOS-eZ80f91 --kernel /pfad/zu/FreeRTOS-Kernel --out build/freertos-wrap
python3 tests/test_freertos_blocking.py build/ez80/qemu-system-ez80 build/freertos-blocking/probe.bin
python3 tests/test_freertos_blocking.py build/ez80/qemu-system-ez80 build/freertos-wrap/probe.bin
```

Ohne `--scenario` baut das Skript weiterhin die bisherige Präemptionsprobe.
Für den Überlauflauf wird nur die kopierte Konfiguration im Ausgabeverzeichnis
um den Starttick ergänzt. Die eingebundenen Original-ASM-Dateien bleiben
unverändert; der Kernelcheckout wird ebenfalls nicht verändert.

Alle neun Integrationstestskripte bestanden. Unabhängige Neubauten
reproduzieren beide neuen Binaries und ihre Metadaten exakt; auch die
bisherige Präemptionsprobe bleibt bytegleich.

Dieser Nachweis umfasst keine Queues, Semaphoren, dynamische Taskanlage oder
Softwaretimer. Der [Original-Boardstart mit PLL](board-startup.md) ist inzwischen im
RAM-Debugprofil geprüft. Weitere Peripherie bleibt offen.
