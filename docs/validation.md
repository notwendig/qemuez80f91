# Validierung vor Veröffentlichung

Prüfdatum: **29. Oktober 2026**. Die Prüfung verwendet den aktuellen lokalen
QEMU-Build mit dem im Workspace gesicherten Gesamtpatch.

## Ergebnis

- **28/28 lokale Prüfskripte bestanden.**
- **2/2 SDK-Integrationstests mit originaler ZDS-EthernetSC-DLL bestanden.**
- Forth: **237/237 Wörterbuch-Einträge ausgeführt**, 201 Ergebnisprüfungen ohne Fehler.
- Zusätzliche Forth-Regression: 89 Fälle vor und nach Reset bestanden.
- Dokumentation: 131 lokale Markdownlinks in 35 Dokumenten geprüft; keine fehlenden Ziele.
- Python-Syntax, Shellsyntax, Fixture-Hashes und QEMU-Patch-Rückwärtsprüfung erfolgreich.
- RTOS-Setup erneut ausgeführt: öffentliche Basistags plus Patches reproduzieren die Bibliotheksquellen.
- Zusätzlich in einem frischen Projektklon geprüft: zweimaliges Patchsetup
  reproduziert Kernel, TCP/IP und uzlib identisch zu den bisherigen Kompatibilitätsständen.

## Lokaler Lauf

| Skript | Ergebnis | Laufzeit |
| --- | --- | ---: |
| `test_board_startup.py` | bestanden | 4.37 s |
| `test_camelf91.py` | bestanden | 8.13 s |
| `test_camelf91_kit.py` | bestanden | 2.57 s |
| `test_camelf91_words.py` | bestanden | 62.90 s |
| `test_chip_selects.py` | bestanden | 0.97 s |
| `test_cpu_uart.py` | bestanden | 0.87 s |
| `test_cstartup_ops.py` | bestanden | 2.57 s |
| `test_dbgport.py` | bestanden | 0.57 s |
| `test_emac.py` | bestanden | 0.62 s |
| `test_extended_opcodes.py` | bestanden | 13.24 s |
| `test_flash_persistence.py` | bestanden | 0.42 s |
| `test_flash_uart.py` | bestanden | 0.31 s |
| `test_freertos_blocking.py` | bestanden | 3.62 s |
| `test_freertos_tasks.py` | bestanden | 1.92 s |
| `test_freertos_unzip.py` | bestanden | 0.67 s |
| `test_freertos_vectors.py` | bestanden | 0.16 s |
| `test_illegal_traps.py` | bestanden | 2.22 s |
| `test_internal_flash.py` | bestanden | 0.16 s |
| `test_kit.py` | bestanden | 0.41 s |
| `test_kit_buttons.py` | bestanden | 0.47 s |
| `test_kit_frames.py` | bestanden | 6.13 s |
| `test_memory.py` | bestanden | 0.21 s |
| `test_opcode_maps.py` | bestanden | 0.87 s |
| `test_pll.py` | bestanden | 1.32 s |
| `test_rtc.py` | bestanden | 6.48 s |
| `test_smoke.py` | bestanden | 0.21 s |
| `test_timer_irq.py` | bestanden | 0.92 s |
| `test_zds_cstartup.py` | bestanden | 0.21 s |

## Originale Hersteller-DLL

`test_zds_ethernet.py --native` prüfte Initialisierung, Registeransichten,
RAM, Step, Breakpoint, Run/Stop und eine unabhängige QMP-Kontrolle.
`test_zds_flash.py` prüfte Löschen, Programmieren und Rücklesen des internen
Flashs sowie eines externen AMD-Bausteins über dieselbe originale DLL.
Beide verwendeten isolierte QEMU-Instanzen und temporäre Flash-Dateien.

## Reproduzierbarkeit und Grenzen

SHA256 des geprüften QEMU-Binaries: `29ea03fb205c3d8df244ffcffc2ae8aeaa2330fa1df121cd0028bdfc867fea9b`.
Der lokale Prüfpfad war `/tmp/qemuez80f91-build-baseline/qemu-system-ez80`;
für andere Rechner ist ein eigener Build gemäß [Erste Schritte](getting-started.md) erforderlich.

Die Einzelergebnisse und Logs werden lokal unter `build/validation/` erzeugt.
Die Forth-Eintragsabdeckung steht unter `build/camelf91-words/report.json`.
Diese Buildberichte werden nicht als portable Quellartefakte eingecheckt.

Live-CP/M-/Tastertests gegen eine laufende fremde Firmwareinstanz, ein neuer
DHCP-/TCP-/UDP-Lauf im realen Netz, die ZDS-GUI-Bedienung und echte Hardware
wurden bei diesem Freigabelauf nicht erneut ausgeführt. Ihre Voraussetzungen
und separaten Aufrufe stehen im [Testkatalog](testing.md).
