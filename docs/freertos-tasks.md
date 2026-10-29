# Zwei echte FreeRTOS-Tasks

## Nachweis

FreeRTOS V10.6.1 läuft im Emulator mit dem vom Originalprojekt mitgelieferten
`kernel-V10.6.1.patch`. Unverändert eingebunden sind `cstartup.asm`,
`vectors24.asm`, `llport.asm`, `portmacro.h` und `stdint.h` aus
`notwendig/FreeRTOS-eZ80f91`, Commit
`cc64b750e7a5c6dfd19dd8eb3a644a9243ce10a9`.
Kernel-Basiscommit und SHA-256 aller eingebundenen Quelldateien stehen in
`examples/freertos_tasks/probe.json`.

Zwei statisch angelegte Tasks gleicher Priorität zählen jeweils vier lokale
Durchläufe und senden A beziehungsweise B über UART0. Zwischen Durchläufen
warten sie aktiv auf eine Änderung des Kernel-Tickzählers. Es gibt keinen
freiwilligen Yield und kein Delay: Erst Timer-Präemption lässt den anderen
Task laufen. Erwartete Ausgabe: `BABABABA!`, anschließend DI und HALT.

Der echte Kernel führt Taskanlage, Ready-Listen, Schedulerstart,
`xTaskIncrementTick` und `vTaskSwitchContext` aus. Der Original-Vektorpfad
sichert die Register; `switch` in `llport.asm` speichert den bisherigen SP im
TCB und lädt den SP des nächsten Tasks. Der Interrupt kehrt schließlich in
dessen Kontext zurück. Eine statisch angelegte Idle-Task existiert zusätzlich,
kommt bei den beiden stets bereiten höher priorisierten Tasks aber nicht zum Zug.

Der Integrationstest prüft sieben Timer-Ticks, beide Durchlaufzähler auf vier,
fehlerfreien Abschluss, exakte UART-Ausgabe, die gespeicherten SPs beider TCBs,
den aktiven CPU-Stack und Schutzwerte an beiden Stackuntergrenzen.
Anschließend folgt Systemreset und derselbe vollständige Nachweis erneut.

## Minimaler Anwendungsport

`main.c` enthält nur die benötigten Teile des ursprünglichen `port.c`:
Stackrahmen für neue Tasks, kritische Abschnitte, Timer0-Start und statische
Speicherbereitstellung. Die Probe verwendet drei Stacks mit jeweils 512
24-Bit-Wörtern, also 1536 Bytes. Das Original-`port.c` mit Netzwerk, uzlib und
Heap-Konfiguration wird nicht eingebunden. Softwaretimer und dynamischer
Speicher sind deaktiviert. Board-/PLL-Initialisierung übernimmt weiterhin
nur das bereits getestete RAM-Boot-Profil.

Die Originaldatei `llport.asm` reserviert außerdem einen unbenutzten
64-KiB-CP/M-Bereich bei B80000; deshalb reicht der RAM-Linkerbereich bis BFFFFF.
Der Initialstack beginnt bei B90000. Das Raw-Image ist wegen der
Linkeradressen 444825 Bytes groß; die ROM-Belegung beträgt 12232 Bytes.

## Start und Neubau

```sh
build/ez80/qemu-system-ez80 -M ez80f91-freertos,ram-boot=on -kernel examples/freertos_tasks/probe.bin -icount shift=0 -display none -monitor none -serial mon:stdio
python3 tests/test_freertos_tasks.py build/ez80/qemu-system-ez80
```

Ctrl-A X beendet den angehaltenen Emulator.
Für den Neubau wird ein FreeRTOS-Kernel-Checkout auf Tag V10.6.1 benötigt.
Der im Originalprojekt festgelegte Submodule-Commit ist nicht über den
angegebenen GitHub-Upstream abrufbar; dessen README weist ausdrücklich den
Build aus dem jeweiligen Tag plus mitgeliefertem Patch an.

```sh
git clone https://github.com/FreeRTOS/FreeRTOS-Kernel.git /tmp/ez80-freertos-kernel
git -C /tmp/ez80-freertos-kernel checkout V10.6.1
python3 examples/freertos_tasks/build.py --zds /pfad/zu/ZDSII_eZ80Acclaim!_5.3.5 --freertos /pfad/zu/FreeRTOS-eZ80f91 --kernel /tmp/ez80-freertos-kernel --out build/freertos-tasks
python3 tests/test_freertos_tasks.py build/ez80/qemu-system-ez80 build/freertos-tasks/probe.bin
```

Das Skript kopiert `tasks.c` und `list.c` direkt aus dem festgelegten
Kernelcommit und wendet die relevanten Änderungen des Originalpatches im
Ausgabeverzeichnis an. Der Kernelcheckout wird dabei nicht verändert.
Wine benötigt lokale Unix-Sockets; die Compilerwerkzeuge kommen aus ZDS 5.3.5.

## Ergänzte CPU-Befehle

- RLA/RRA/RLCA/RRCA mit Erhalt von S/Z/PV und Löschen von H/N.
- PEA IX/IY mit vorzeichenbehaftetem Offset und kurzem/langem Stack.
- LD A,(BC/DE) und LD (BC/DE),A.
- Indexregister laden/speichern über HL sowie über IX/IY mit Offset.
- MLT für BC/DE/HL/SP: untere Bytes multiplizieren, Ergebnis auf 16 Bit begrenzen (oberes Byte null).
- ADD/ADC/SUB/SBC A,n mit vollständigen dokumentierten Rechenflags.

Grundlage: UM007715-0415, insbesondere S. 206–211, 246–247, 275–276
und die Beschreibungen der Akkumulatorrotationen und Rechenbefehle.
Gezielte Regressionen stehen in `tests/test_cstartup_ops.py`.

Blockierende Aufrufe, freiwilliger Yield und Ticküberlauf sind inzwischen
mit einer separaten [Kernelprobe](freertos-blocking.md) geprüft.
Der [Original-Boardstart](board-startup.md) ist inzwischen im RAM-Debugprofil
geprüft. Weitere Peripherie und Flash-Kaltstart bleiben offen.
Dieser Nachweis ist kein vollständiger CPU- oder F91-Kompatibilitätstest.
