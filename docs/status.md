# Entwicklungsstand

Stand der Dokumentation: **29. Oktober 2026**. Maßgeblich für Quellversionen
sind die Gitlinks des jeweiligen Commits und die Hashes der Testfixtures.
Der Emulator ist funktional getestet, aber keine vollständige eZ80F91- oder
Hardwarekompatibilität wird behauptet.

## Implementierter und geprüfter Umfang

| Bereich | Nachweise |
| --- | --- |
| CPU | Z80/ADL, Präfixe, 16-/24-Bit-Register und Adressen, Stacks, Calls/Returns, TRAP und erweiterte Opcodes |
| Speicher | Interner RAM/Flash/EMAC-RAM, CS0–CS3, Remapping, Prioritäten und AMD-Flash |
| UART0 | Polling, RX-FIFO, Interrupts, Pinmux und Taktfreigabe |
| Timer/IRQs | Timer0 und Timer1, Vektoren, Prioritäten, EI-Verzögerung, RETI und Moduswechsel |
| Takt und RTC | Board-Oszillator-/PLL-Start, funktionale Lock-Verzögerung, Kalender und ZTP-RTC-ABI |
| Ethernet | Shared-RAM-Deskriptoren, TX/RX, Überlauf, Filter, Interrupts und Clause-22-Management |
| Debugger | Originale ZDS EthernetSC-DLL, Register/RAM, Run/Stop/Step, Breakpoints, Flash und Scan Device |
| Kit | 5×7-Matrix, vollständige Scan-Veröffentlichung, Taster SW1–3 und Reset |
| CamelForth | Kernkorrekturen, 237 ausgeführte Wörterbucheinträge, 201 Ergebnisprüfungen und 89 Reset-Regressionen |
| FreeRTOS | Originaler C-/Boardstart, Tasks/Kontextwechsel, Yield/Delay, kritische Abschnitte und Ticküberlauf |
| CP/M 2.2 | Gzip-Ramdisk, CRC-/Größenfehler, BIOS-TRAPs und separates Live-Telnet-Szenario |
| ZTP TCP/UDP | Originalbeispiel mit RAM-Dateisystem, DHCP von nadibox sowie UDP-/TCP-Echo |

Die tatsächlich bei einer Veröffentlichung ausgeführten Prüfungen stehen in
[Validierung](validation.md). Der [Testkatalog](testing.md) trennt lokale,
SDK-abhängige und Live-Prüfungen.

## Bekannte Grenzen

- Kein vollständiger Befehlssatz-/Peripherie-Kompatibilitätsnachweis, keine
  taktgenaue CPU, keine elektrische Bus- oder LED-Simulation.
- UART-Baud-/Schieberegistertiming und weitere Geräte-/Interruptfälle sind
  nicht vollständig modelliert. Aus einzelnen erfolgreichen Firmwaretests
  folgt kein Nachweis aller Registerkombinationen.
- Der PHY-Status bildet nicht alle herstellerspezifischen Register ab.
  Insbesondere liest FreeRTOS Geschwindigkeit/Duplex aus AMD-Register 18;
  dessen bisheriger Nullwert kann `10MBPS, HALF_DUPLEX` anzeigen. Das ist
  keine Messung der Geschwindigkeit des Host-Netzwerks.
- Die Kit-Anzeige zeigt jeden vollständigen Scan. Sie verlangt keine zwei
  identischen Bilder; eine solche Bedingung hatte fortlaufende Laufschrift
  blockiert und wurde entfernt.
- Ein Gastpufferwechsel während des Scans kann im realen Latch-Datenstrom
  gemischte Zeilen erzeugen. Das Fenster verändert die Gastfirmware nicht.
- Netzwerkprüfungen hängen von Bridge, DHCP und Gegenstelle ab. Ein bestandener
  lokaler MAC-Test bestätigt nicht automatisch das komplette externe Netz.
- ZDS-/Nexus-/ZTP-Builds benötigen die separat installierten Herstellerwerkzeuge.
  Die SDK-Dateien sind kein Bestandteil dieses Repositories.

## Nächste Entwicklungsaufgaben

1. Hersteller-PHY-Diagnose einschließlich ausgehandelter Geschwindigkeit und
   Duplexstatus konsistent ergänzen.
2. Weitere CPU-/Peripheriefälle mit unabhängigen Referenzen bzw. Hardware vergleichen.
3. Zusätzliche FreeRTOS-Kernelpfade und Geräte schrittweise durch gezielte
   Ausführungstests absichern.

Details: [Architektur](architecture.md), [Ethernet](emac.md),
[Kit](kit.md), [CamelForth](camelf91.md), [Quellen](sources.md).
