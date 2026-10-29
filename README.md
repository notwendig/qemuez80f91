# qemuez80f91

Eigenständiges Entwicklungsprojekt für eine QEMU-Systememulation des
Zilog eZ80F91 (eZ80Acclaim!).

## Starten

```sh
./start.sh                  # Debugport 4040
./start.sh dbgport 4041     # anderer Debugport
./start.sh --run            # gespeichertes Flash ohne Debugger starten
./start.sh --kit            # Debugstart mit Kit-LED-Fenster
./start.sh --run --kit      # Flash-Start mit Kit-LED-Fenster
```

Öffnet ein eigenes UART-Terminal mit dem Titel `eZ80f91.<port>` und startet
QEMU mit Scan Device; die CPU wartet auf den Debugger. Bereits laufende
Instanzen mit demselben Debugport und anderweitig belegte Ports werden
abgewiesen. Strg-C oder Schließen des UART-Fensters beendet QEMU und speichert
Flash. Benötigt `gnome-terminal` oder `xterm`.
Mit `--run` läuft die CPU unmittelbar ab dem Resetvektor im Flash los.
Der Starter nutzt auch im Debugbetrieb `br0` mit dem vorhandenen QEMU-Bridge-Helper und
wartet vor dem CPU-Start auf die Portfreigabe. DHCP liefert die nadibox.
Die AMD-PHY-Adresse ist 31; `icount shift=5,sleep=off` steuert die virtuelle
Zeit wie beim TCP/UDP-Demo. UART-Protokolle liegen unter
`/tmp/ez80f91-<uid>/<port>.uart.log`.
`--kit` zeigt die 7×5-LED-Matrix des Development Kits in einem eigenen Fenster.
Die Firmware steuert sie über 800000h/800001h; CS2 muss diesen Bereich freigeben.
Die Anzeige integriert die Multiplexzyklen. [Register und Grenzen](docs/kit.md).
Internes Flash wird aus `ez80f91_0.<port>` im aktuellen Arbeitsverzeichnis
geladen. Externe Flash-Dateien werden erst beim Aktivieren des jeweiligen
Chip Selects geladen. Fehlende Inhalte sind `FF`; beim Beenden wird gespeichert.
Mit `QEMU_EZ80=/pfad/qemu-system-ez80` lässt sich die QEMU-Datei auswählen.
Die bisherigen Root-Starter `start.f24` und `start.demo` sind durch `start.sh`
ersetzt; die projektspezifischen Hilfsprogramme stehen weiterhin bereit.

## ZTPDemo in ZDS II debuggen

Zuerst `./start.sh`, danach `./start.zds-demo.sh` aufrufen. Der zweite Starter
öffnet `build/ztp-demo-zds/ZTPDemo_QEMU.zdsproj`, verbindet den Debugger und
lädt das RAM-Image. Mit F5 fortsetzen. Diese lokale Projektkopie setzt
RAM bei 000000h–07FFFFh und deaktiviert das interne Flash während der
Debugsitzung. Das installierte Herstellerprojekt mit RAM-Konfiguration und
Flash-Target passt nicht zu dieser Speicherbelegung; der Download scheitert
dort ab 040000h. Für Flash-Boot stattdessen die separat gelinkte Datei
`build/ztp-demo-flash/ztpdemo-flash.hex` verwenden.

## CAMEL24 in ZDS II starten

```sh
python3 tools/zds/f24.py
```

Startet CAMEL24, QEMU, Ethernet-ZDI und ZDS II mit Quellcode-Debugging.
[Bedienung und Voraussetzungen](docs/start-f24.md).

## FreeRTOS-eZ80f91 bauen

```sh
python3 subprojects/FreeRTOS-eZ80f91/setup-dependencies.py
```

Danach `subprojects/FreeRTOS-eZ80f91/EZ80F910300ZCOG.zdsproj` in ZDS II
öffnen und die Konfiguration **Debug** bauen. Die benötigten öffentlichen
Bibliotheksversionen und eZ80-Patches richtet das Setup wiederholbar ein.
[Build-Hinweise](subprojects/FreeRTOS-eZ80f91/BUILD.md).

## TCPUDPDemo starten

```sh
python3 -m tools.demo
```

Startet das originale ZTP-Demo mit RAM-Dateisystem und UART-Konsole an
der Netzwerkbridge `br0`. DHCP kommt immer von **nadibox (192.168.77.1)**. Login: `anonymous` / `anonymous`; Beenden: Strg+C oder Strg+].
Automatischer Netzwerk-Test: `python3 -m tools.demo --test`.
[Bedienung und Grenzen](docs/ztp-tcpudp.md).

QEMU bietet `--dbgport=4040` einschließlich **Scan Device** auf UDP 3000.
Mit Demo: `python3 -m tools.demo --dbgport=4040`; mit CAMEL24: `python3 tools/zds/f24.py`.
[Direktstart und Debugprotokoll](docs/zds-ethernet.md).

## Stand

Die [RTC-Kalenderregister](docs/rtc.md) unterstützen den originalen ZTP-SNTP-
Client. Das MAC-Modell meldet Empfangsüberläufe per RxOVR-Deskriptor, damit
der Zilog-Treiber den Empfang anschließend wieder freigeben kann.

CS0–CS3 bilden RAM oder AMD-Flash dynamisch anhand ihrer Steuerregister ab.
Bausteinauswahl beispielsweise mit `python3 -m tools.demo --cs3 flash`:
[Chip-Selects, Prioritäten und Tests](docs/chip-selects.md).

Der F91-Ethernet-MAC kann jetzt Frames über ein QEMU-Netzwerkbackend senden
und empfangen: [Anbindung, Register, Tests und Grenzen](docs/emac.md).
Mit ZDS II: `python3 tools/zds/f24.py --nic 'socket,connect=127.0.0.1:5555'`.

ZDS II kann jetzt über die unveränderte Ethernet-Smart-Cable-DLL mit QEMU
debuggen: [Start, Konfiguration und Grenzen](docs/zds-ethernet.md).


**Original-Boardstart mit Oszillator/PLL und anschließendem FreeRTOS-Betrieb geprüft.**
Arbeitsstand: [Fortsetzungsnotizen](docs/PAUSE.md).

Das originale ZTP-TCPUDPDemo läuft mit dem vorgesehenen RAM-Dateisystem:
DHCP, UART-Login sowie 1000-Byte-UDP- und 4000-Byte-TCP-Echo sind geprüft.
[Build, Test und Grenzen](docs/ztp-tcpudp.md).

Weitere 168 Opcode-Encodings sind ergänzt: Indexbytes, BCD/Bit-Tests,
Block-I/O, RST/RETN und SLP. Ausführungstests und Grenzen:
[Erweiterte Opcodes](docs/extended-opcodes.md).

Die Ziele `ez80f91-minimal` und `ez80f91-freertos` führen eine getestete
Teilmenge des eZ80-Befehlssatzes aus. Speichersteuerregister und Flash-/RAM-
Remapping sind implementiert; UART0 unterstützt Polling, RX-FIFO und Interrupts.
Die Flash-Informationsseite ist über I/O les-/programmier-/löschbar:
[Flash und UART](docs/flash-uart.md).

Ein echtes, mit ZDS übersetztes C-Testprogramm läuft mit dem unveränderten
C-Startup aus `notwendig/FreeRTOS-eZ80f91`: BSS/DATA-Initialisierung,
C-main, UART-Ausgabe und Neustart sind geprüft. Zusätzlich läuft die originale
Vektorinitialisierung samt Timer0-ISR und Register-Sicherungswrapper.
Der FreeRTOS-V10.6.1-Scheduler führt zwei Tasks mit dem originalen
Kontextwechsel aus `llport.asm` aus. Sieben Timer-Ticks, getrennte Taskstacks
und Reset sind geprüft: [FreeRTOS-Tasks](docs/freertos-tasks.md).
Zusätzliche Proben prüfen `taskYIELD`, verschachtelte kritische Abschnitte,
`vTaskDelay`, Idle-Ausführung und den 24-Bit-Ticküberlauf:
[Blockieren und Aufwecken](docs/freertos-blocking.md).
Der unveränderte `init_params_f91.asm` durchläuft jetzt den gesamten Startpfad
im RAM-Debugprofil: [Boardstart und PLL](docs/board-startup.md).
Als festes Sub-/Testprojekt läuft zusätzlich CAMELF91-24-Bit-Forth mit einem
Polling-Konsolenadapter: [CamelForth](docs/camelf91.md). Vier reproduzierte
Kernfehler sind mit separatem Patch und 83 Testfällen korrigiert:
[Analyse und Fixes](docs/camelf91-analysis.md).
Details zum C-Start: [FreeRTOS-C-Startup](docs/freertos-boot.md).

Allgemeiner Build und erste ROMs: [Ausführbarer Stand](docs/first-execution.md).
Alle QEMU-Änderungen sind als reproduzierbarer Patch im Projekt gesichert.

Dieses Projekt ist unabhängig von `zilogz80-code/qemu80`. Dessen NMOS-Z80-Kern
und die dort entworfene 16-KiB-Banking-MMU werden nicht übernommen: Sie bilden
den eZ80 mit ADL-Modus und die integrierten F91-Komponenten nicht ab.

## Ziel

- eZ80-Befehlssatz mit Z80- und ADL-Modus, 24-Bit-Registern und Adressen.
- Korrekte Moduswechsel, Befehlspräfixe, Stack- und Interruptbehandlung.
- Modell des eZ80F91 mit internem Flash/RAM, externer Speicheranbindung
  und schrittweise ergänzter Peripherie.
- UART-Konsole zum Starten und Prüfen eigener Firmware.
- Einbindung als eigenes CPU- und Maschinenziel in eine festgehaltene
  QEMU-Version.

Die konkrete Platine und deren externe Speicherbelegung sind noch offen.
Es werden keine Adressen oder Peripheriefunktionen ohne Prüfung anhand des
F91-Datenblatts bzw. des Schaltplans festgelegt.

## Nächste Entwicklungsschritte

1. Weitere Kernelpfade wie Queues/Semaphoren und dynamische Taskanlage prüfen.
2. CPU-Befehlssatz und Flash-Kaltstart schrittweise ergänzen.
3. Weitere Timer und Geräte schrittweise anbinden.
4. UART-FIFO, Interrupts und Baudtiming sowie weitere Geräte ergänzen.
5. Verhalten mit unabhängigen Referenzen bzw. Hardware vergleichen.

QEMU 11.1.2 und die reguläre TCG-Anbindung sind festgelegt:
[QEMU-Basis](docs/qemu-base.md).

Die erste Quellenprüfung für CPU/F91, Reset, Speicher und UART0 ist in
[Implementierungsgrundlage](docs/ez80f91-baseline.md) dokumentiert.

Details: [Architektur](docs/architecture.md), [Quellen](docs/sources.md).
