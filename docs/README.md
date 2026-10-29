# Dokumentation

## Einstieg und Betrieb

| Dokument | Inhalt |
| --- | --- |
| [Erste Schritte](getting-started.md) | Voraussetzungen, Checkout, QEMU-Build, erster ROM-Start und Starter |
| [Status](status.md) | Aktuelle Fähigkeiten, bekannte Grenzen und Prüfumfang |
| [Architektur](architecture.md) | CPU, Geräte, Speicher, Zeitmodell und Debugger |
| [Entwicklung](development.md) | Repositories, Patches, Buildprodukte, Aufräumen und Veröffentlichung |
| [Tests](testing.md) | Lokale Regressionen, SDK-Tests und Tests an laufender Firmware |
| [Quellen und Lizenzen](licenses.md) | Herkunft und vorhandene Lizenzhinweise |

## Firmwareprojekte

| Projekt | Dokumente |
| --- | --- |
| CamelForth | [Integration und Build](camelf91.md), [ZDS-Start](start-f24.md), [Kernkorrekturen](camelf91-analysis.md), [Worttest](camelf91-words.md), [Taster/Matrix](camelf91-kit.md) |
| FreeRTOS | [Projekt-README](https://github.com/notwendig/FreeRTOS-eZ80f91), [Build](https://github.com/notwendig/FreeRTOS-eZ80f91/blob/master/BUILD.md), [C-Startup](freertos-boot.md), [Tasks](freertos-tasks.md), [Blockieren/Yield](freertos-blocking.md), [Boardstart](board-startup.md) |
| BSP | [Bibliothek und API](https://github.com/notwendig/ez80f91bsp) |
| ZTP | [Originales TCP/UDP-Demo](ztp-tcpudp.md) |

## Geräte und Debugging

- [Speicher und Chip Selects](chip-selects.md)
- [Flash und UART](flash-uart.md)
- [Timer, Interrupts und Vektoren](timer0-interrupts.md)
- [RTC](rtc.md)
- [Ethernet-MAC und PHY](emac.md)
- [Kit-Matrix und Taster](kit.md)
- [Ethernet Smart Cable / ZDS II](zds-ethernet.md)
- [Erweiterte CPU-Befehle](extended-opcodes.md)

## Implementierungsgrundlagen

[QEMU-Basis](qemu-base.md) beschreibt die festgelegte Upstream-Version.
[Quellen](sources.md) und [F91-Grundlagen](ez80f91-baseline.md) dokumentieren
Herstellerreferenzen und die anfängliche Register-/Resetprüfung.
[Erste Ausführung](first-execution.md) hält den frühen CPU-/UART-Meilenstein
fest; seine historischen Einschränkungen sind nicht die aktuelle Funktionsliste.
Maßgeblich für den heutigen Umfang ist [Status](status.md).
