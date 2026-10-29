# Testkatalog

Die Tests sind eigenständige Python-Skripte und verwenden QMP/GDB, UART und
kleine Gastprogramme. Sie werden direkt aufgerufen, nicht über pytest.
`QEMU_EZ80` sollte auf den aktuellen Build zeigen. Lokale Unix-/TCP-Sockets
müssen erlaubt sein; die meisten Tests brauchen keine Netzwerkbridge.

## Lokale Emulator- und Fixturetests

```sh
export QEMU_EZ80="$PWD/build/ez80/qemu-system-ez80"
python3 tests/test_smoke.py "$QEMU_EZ80"
python3 tests/test_cpu_uart.py "$QEMU_EZ80"
python3 tests/test_memory.py "$QEMU_EZ80"
python3 tests/test_camelf91.py "$QEMU_EZ80"
```

| Gruppe | Skripte |
| --- | --- |
| CPU/Decoder | `test_smoke.py`, `test_cpu_uart.py`, `test_cstartup_ops.py`, `test_extended_opcodes.py`, `test_opcode_maps.py`, `test_illegal_traps.py` |
| Speicher/Flash | `test_memory.py`, `test_chip_selects.py`, `test_flash_uart.py`, `test_internal_flash.py`, `test_flash_persistence.py` |
| Takt/Timer/RTC | `test_timer_irq.py`, `test_pll.py`, `test_rtc.py` |
| MAC/Debugger | `test_emac.py`, `test_dbgport.py` |
| Gespeicherte ZDS-/FreeRTOS-Images | `test_zds_cstartup.py`, `test_freertos_vectors.py`, `test_freertos_tasks.py`, `test_freertos_blocking.py`, `test_board_startup.py` |
| Kit | `test_kit.py`, `test_kit_frames.py`, `test_kit_buttons.py` |
| Forth | `test_camelf91.py`, `test_camelf91_words.py`, `test_camelf91_kit.py` |

Diese Skripte erhalten den Emulator als erstes Argument. Decoderprüfungen
benötigen zusätzlich den lokalen QEMU-Quellbaum und einen Host-C-Compiler.
Die FreeRTOS-/ZDS-Fixturetests bauen nicht jedes Mal die Firmware neu;
Image-Hashes und Metadaten werden geprüft.

## Vollständiger Forth- und Kit-Lauf

```sh
make -C subprojects/CAMELF91_24
python3 tests/test_camelf91_words.py "$QEMU_EZ80"
python3 tests/test_camelf91_kit.py "$QEMU_EZ80"
python3 tests/test_kit_frames.py "$QEMU_EZ80"
```

Die ersten beiden verwenden standardmäßig das native Debug-HEX und die
zugehörige Mapdatei. `--hex` und `--map` wählen einen anderen Build.
Der Worttest protokolliert alle erreichten Wörterbuch-Einsprünge und schlägt
bei fehlender Abdeckung fehl. [Einzelheiten und Forth-Datei](camelf91-words.md).

Der Frame-Test hält den Gast nach jeder Zeile an und wechselt das Bild nach
jedem vollständigen Scan. Er prüft sowohl das Halten des vorherigen Bildes
während eines Teilscans als auch den Fortschritt einer fortlaufend geänderten
Laufschrift. [Anzeigeverhalten](kit.md).

## CP/M-Dekompression auf dem Host

Nach eingerichtetem FreeRTOS-Checkout und uzlib:

```sh
python3 tests/test_freertos_unzip.py
```

Der Test übersetzt den tatsächlichen Wrapper und uzlib mit dem Hostcompiler.
Er prüft das Original-Ramdiskfixture, CRC, Abbruchfälle und Ausgabegrenzen;
er benötigt keinen laufenden Gast und keinen QEMU-Parameter.

## Originale ZDS-/Nexus-DLL

Mit installierten Herstellerwerkzeugen, Wine und MinGW:

```sh
python3 tests/test_zds_ethernet.py --qemu "$QEMU_EZ80" \
  --zds "$ZDS_HOME" --sdk /pfad/NexusSDK_1.1 --native --sdk-scan
python3 tests/test_zds_flash.py --qemu "$QEMU_EZ80" \
  --zds "$ZDS_HOME" --sdk /pfad/NexusSDK_1.1
```

Diese Tests benutzen freie lokale Ports und eigene Flash-Temporärdateien.
Sie sind vom normalen Hardware-/Fixturelauf getrennt, da SDK und Windows-DLL
zusätzliche Voraussetzungen darstellen.

## Laufende Firmware und reales Netz

```sh
python3 tests/test_freertos_buttons.py /tmp/ez80f91-1000/4040.qmp
python3 tests/test_freertos_cpm.py 192.168.77.26
python3 -m tools.demo --test
```

Diese Aufrufe sind manuelle Integrationstests: Der passende Gast muss laufen,
QMP/IP müssen stimmen und CP/M kann beim ersten Entpacken mehrere Minuten
benötigen. Der Tastertest verwendet die aktuelle FreeRTOS-Linker-Map.
Der Demo-Netzwerktest erwartet nadibox-DHCP und reale UDP-/TCP-Gegenstellen.
Sie gehören nicht in einen unkontrollierten `test_*.py`-Glob.

## Berichte und Aussagekraft

[Validierung](validation.md) dokumentiert die tatsächlich ausgeführten
Freigabeprüfungen. Berichte und Laufzeitlogs liegen unter `build/` bzw. in
Test-Temporärverzeichnissen. Ein erfolgreicher Test bestätigt das beschriebene
Szenario; er ist kein vollständiger Nachweis aller Opcodes, Registerkombinationen
oder Hardware-Timings.
