# CAMEL24 mit einem Kommando in ZDS II debuggen

Im Projektverzeichnis:

```sh
python3 tools/zds/f24.py
```

Der Starter baut bei Bedarf die korrigierten CAMEL-Quellen mit Quellzeilen und
OMF695-Symbolen, erzeugt ein separates ZDS-Projekt in `build/f24/`, startet
QEMU im getesteten `ez80f91-freertos,ram-boot=on`-Profil und die Ethernet-ZDI-
Brücke. Anschließend öffnet er ZDS II, stellt Ethernet Smart Cable auf
`127.0.0.1:4040` ein, lädt `camel.lod` und hält am Programmeinstieg `_main`
in `CAMLF91e.asm` an. Der Starter bestätigt „Bereit“ erst nach erfolgreicher
Rückmeldung aus dem ZDS-Befehlsskript. Die UART-Konsole ist mit dem Terminal
des Starters verbunden.

In ZDS II: **F5** fortsetzen, **F11** Step Into, **F10** Step Over,
**Ctrl+F5** anhalten, **Ctrl+Shift+F5** zurücksetzen.
Nach F5 lassen sich im Starter-Terminal Forth-Befehle eingeben.
**Strg-C im Starter-Terminal** beendet die gestarteten Prozesse.
Ein zweiter Start wird durch eine Prozesssperre verhindert.

Der erste Start benötigt Wine und `i686-w64-mingw32-gcc` ist nur für den
separaten Nexus-Integrationstest erforderlich. Der CAMEL-Build verwendet die
installierten ZDS-Assembler-/Linkerprogramme. Standardinstallation:
`~/.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5`.
Der IDE-/Buildprozess verwendet das eigene Wine-Präfix
`/tmp/qemuez80f91-zds-wine`. Das bestehende ZDS-Installationsverzeichnis
bleibt unverändert; die Buildkopie wird getrennt vom nativen CAMEL-Projekt
gepflegt.

Weitere Aufrufe:

```sh
python3 tools/zds/f24.py --rebuild
python3 tools/zds/f24.py --prepare-only
python3 tools/zds/f24.py --qemu /pfad/qemu-system-ez80 --zds /pfad/ZDSII
```

Alternativ setzen `QEMU_EZ80` und `ZDS_HOME` die jeweiligen Standardpfade.
Standard-QEMU ist `/tmp/qemuez80f91-build-baseline/qemu-system-ez80`;
bei Bedarf zuerst nach [first-execution.md](first-execution.md) bauen.
Die Ports TCP 4040 (ZDS), UDP 3000 (Scan Device) und TCP 4444 (UART) müssen frei
sein. QEMU startet die Brücke über `--dbgport=4040`; GDB nutzt einen privaten
Unixsocket. `--gdb-port` bleibt nur als kompatibles Starterargument erhalten. Der zuvor manuell gestartete Debugstack muss vorher beendet werden.

Diagnose: `build/f24/zds-session.log`, `qemu.log` (einschließlich Debugbrücke), `ide.log`
und `build.log`. Das Startskript der IDE liegt unter `build/f24/start.cmd`.
`externalAutoSelect` ist im generierten Target abgeschaltet: es gibt in diesem
RAM-Debugprofil keinen externen Flashbaustein zu identifizieren.

Geprüft am 28.10.2026 mit ZDS II 5.3.5: automatischer Projektstart, Ethernet-
Verbindung, fehlerfreier Download von `camel.lod`, Quellcodeanzeige und Halt am
Einstieg (PC 00039Bh). Das mit Debugdaten gebaute Rohimage ist bytegleich mit
dem durch 89 CAMEL-Testfälle geprüften `examples/camelf91/camel.bin`.
Die Einschränkungen des Emulators und der ZDI-Brücke stehen in
[zds-ethernet.md](zds-ethernet.md).

## ZDS-II-Ansichten

Der Starter öffnet nach dem Debug-Download alle zehn Debugansichten:
Registers, Special Function Registers, Clock, Memory, Watch, Locals,
Call Stack, Symbols, Disassembly und Simulated UART Output. Bereits sichtbare
Ansichten bleiben geöffnet; es entstehen dadurch keine zusätzlichen
Memory-/SFR-Fenster. Die Befehlskennungen werden aus den Accelerator-Ressourcen
der installierten IDE gelesen. Memory wird auf den Speicherraum „Memory“
gestellt; das aktive Quellfenster wird maximiert. Diagnose: `build/f24/views.log`.
Zum Deaktivieren: `python3 tools/zds/f24.py --no-views`.

Das Ansichten-Hilfsprogramm benötigt `i686-w64-mingw32-gcc` und wird bei Bedarf
aus `tools/zds/views.c` gebaut. Clock kann beim Ethernet Smart Cable „not
supported“ anzeigen. Die simulierte IDE-UART ist nicht QEMUs UART: Forth-I/O
läuft weiterhin im Fenster „CAMEL24 – App-Konsole“. Locals/Call Stack sind
abhängig von vorhandenen Debug-/Frameinformationen des Assemblerprogramms;
Watch zeigt Werte erst nach dem Hinzufügen von Ausdrücken.

Der vollständige Registerabruf wurde zusätzlich gegen die installierte Nexus-
DLL geprüft. Deren ausgeliefertes GET_REGS_ALL-Algorithmusende verwendet
`R16=16` beim Wiederherstellen von AF/MBASE. Die Brücke behandelt diesen
Nexus-Kompatibilitätsfall als AF-Lesezugriff; dies ist keine zusätzliche
siliziumseitige ZDI-Funktion.

## Gast-Ethernet-MAC

`--nic` reicht ein Netzwerkbackend an den F91-MAC weiter, zum Beispiel
`python3 tools/zds/f24.py --nic 'socket,connect=127.0.0.1:5555'`. Standard ist `none`.
Der Peer muss das QEMU-Ethernet-Socket-Protokoll sprechen. Dies ergänzt den
Gast-MAC; CAMEL24 benötigt weiterhin einen eigenen Netzwerktreiber/Stack.
[Registermodell, Test und Grenzen](emac.md).

## Externe Chip-Selects

`--cs0` bis `--cs3` wählen beim Start `ram`, `flash` oder `none` für die
entsprechende externe Bank. Danach steuert die Firmware die Fenstergrenzen
und Freigaben dynamisch über die F91-Register. Standard: CS0 Flash, CS1–CS3 RAM.
[Abbildung und Grenzen](chip-selects.md).
