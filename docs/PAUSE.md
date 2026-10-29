# Arbeitsstand – 2026-10-27

CAMELF91-Kern analysiert und vier reproduzierte Fehler korrigiert.

## Erreicht

- QEMU 11.1.2 mit eigenem eZ80F91-TCG-Ziel.
- ADL-/Z80-Modi, Teilbefehlssatz, Register/Stacks und gemischte CALLs.
- Speicherregister, Flash-/RAM-Remapping und FreeRTOS-RAM-Boardprofil.
- Funktionales UART0-Polling mit Empfang, Pinmux und Clock-Gating.
- Echter ZDS-C-Start mit Original-cstartup.asm; BSS/DATA und Reset geprüft.
- Timer0, Prioritätscontroller, EI-Verzögerung, RETI/RETI.L.
- Original-vectors24.asm: Initialisierung, set_vector, Trampolin, IRQ-Wrapper,
  drei Timerinterrupts, Ausgabe TTT und Register-/Stackerhalt; auch nach Reset.
- FreeRTOS V10.6.1 mit Originalprojekt-Patch: zwei echte Tasks, sieben
  präemptive Timer-Ticks, Original-llport.asm, eigene Stacks und Reset geprüft.
- Freiwilliger Yield mit tasklokaler kritischer Verschachtelung und Interruptstatus.
- `vTaskDelay`, Idle-Task und exakte Weckzeitpunkte, auch über den
  24-Bit-Kernel-Ticküberlauf; beide Varianten samt Reset geprüft.
- Unveränderter `init_params_f91.asm`: Speicher/Stack/Vektoren/Takt/C-Startup,
  danach echter Kernelbetrieb, mit Original-Oszillator und aktivierter PLL.
- PLL-Register/IRQ, Timer-Taktwechsel und Prioritätskonkurrenz PLL/Timer
  sind einschließlich Reset geprüft.
- CAMELF91_24 als Git-Submodul auf b975f3ac festgelegt; Originalkern und
  Originalstart mit separatem Polling-BSP gebaut. Interaktives Forth-Rechnen,
  Kompilieren, Schleifen/Verzweigungen, Speicher und Dictionary-Reset geprüft.
- CAMEL-Kernpatch: DEPTH, FM/MOD, M+ und ACCEPT korrigiert; 83 Forth-Fälle
  jeweils vor und nach Reset geprüft. Das Submodul selbst bleibt unverändert.

Details: [CAMEL-Analyse/Fixes](camelf91-analysis.md), [CAMELF91_24](camelf91.md), [Boardstart/PLL](board-startup.md), [Yield/Delay/Ticküberlauf](freertos-blocking.md), [FreeRTOS-Tasks](freertos-tasks.md), [C-Startup](freertos-boot.md), [Timer/Vektoren](timer0-interrupts.md).
Der gesamte QEMU-Stand liegt in `patches/0001-ez80f91-minimal.patch`.
Der ignorierte Checkout `qemu/` steht auf `ez80f91-dev`, Basiscommit
4fc49f46dc95d4a27de2509e7fceb2931e91faeb.

## Sitzung und Prüfung

Projekt: `/home/juergen/Projects/eZ80Acclaime!/qemuez80f91`.
Build: `/tmp/qemuez80f91-build-baseline/qemu-system-ez80`.
FreeRTOS-Quellprüfung: `/tmp/FreeRTOS-eZ80f91-review`.
ZDS-Wineprofil: `/tmp/qemuez80f91-zds-wine`.

Alle Integrationstests mit dem jeweiligen QEMU-Binary als erstem Argument:

- `tests/test_smoke.py`
- `tests/test_cpu_uart.py` (lokaler Unix-Socket nötig)
- `tests/test_memory.py`
- `tests/test_cstartup_ops.py`
- `tests/test_zds_cstartup.py`
- `tests/test_timer_irq.py`
- `tests/test_freertos_vectors.py`
- `tests/test_freertos_tasks.py`
- `tests/test_freertos_blocking.py` (normale und Überlaufvariante)
- `tests/test_pll.py`
- `tests/test_board_startup.py` (Oszillator- und PLL-Variante)
- `tests/test_camelf91.py` (lokaler Unix-Socket nötig)

Alle zwölf Testskripte bestanden. Die CamelForth-Probe sowie die Board-Images
und Metadaten sind bytegenau reproduzierbar. Gesamtpatch auf unveränderter Basis geprüft;
Checkpatch: null Fehler, nur der allgemeine MAINTAINERS-Hinweis.

Buildanleitung: [Erste Ausführung](first-execution.md).

## Nächste Schritte

Der Scheduler-Nachweis ist unter `examples/freertos_tasks/` gesichert.
Kernel: `/tmp/ez80-freertos-kernel`, Tag V10.6.1. Der im Originalprojekt
referenzierte Submodule-Commit ist bei GitHub nicht abrufbar; stattdessen
wird gemäß dessen README V10.6.1 mit dem mitgelieferten Patch verwendet.
Reproduktionsbuild: `/tmp/ez80-tasks-repro`.

Die neuen Proben liegen unter `examples/freertos_tasks/blocking/`.
Builds: `build/freertos-blocking`, `build/freertos-wrap`.
Der Builder unterstützt `--scenario preempt`, `blocking`, `wrap`, `board` und `pll`.
Boardproben: `examples/freertos_tasks/board/`; Builds unter
`build/freertos-board` und `build/freertos-pll`.

CAMEL-Quellen: `subprojects/CAMELF91_24`, Commit
`b975f3acac08c70c05d951aad22e5c1824446206`. Build/Tests unter
`examples/camelf91/`, Buildausgabe `build/camelf91`. Der originale BSP-Commit
ist nicht abrufbar; der Test verwendet ausdrücklich den lokalen Polling-Adapter.
Kernpatch: `patches/camelf91/0001-fix-24bit-core.patch`; Anwendung nur in der
Buildkopie. Neues Testimage 9350 Bytes. Analyse: `docs/camelf91-analysis.md`.

Als nächste Kernelpfade bieten sich Queues/Semaphoren, dynamische Taskanlage
und Softwaretimer an. Flash-Kaltstart und weitere CPU-Befehle bleiben offen.
Der Boardstart ist bisher im RAM-Debugprofil geprüft; das PLL-Modell verwendet
eine funktionale Lock-Verzögerung, keine analoge Simulation.

Keine vollständige F91-Kompatibilität, kein NMI, keine Timer1–3,
UART-FIFO und -IRQs sowie der funktionale EMAC sind inzwischen ergänzt;
Baud-/Schieberegistertiming bleibt offen. Siehe die neueren Abschnitte unten.

## Ethernet-ZDI / ZDS II (2026-10-28)

Neue Brücke unter `tools/zds/`, Starter `python3 tools/zds/launch.py`.
QEMU besitzt dafür 24 GDB-Registerslots und ein Debug-Portfenster.
Echte installierte `nxEz80EthernetSC.dll` per Nexus-API unter Wine geprüft:
Initialisierung, Reset, Register, RAM, Step, Run/Stop und Breakpoint-Ereignis.
Test: `python3 tests/test_zds_ethernet.py`. Details und verbleibende Grenzen:
[zds-ethernet.md](zds-ethernet.md). Keine GUI-Ende-zu-Ende-Prüfung, kein
Flash-Programmierpfad und keine UDP-Discovery.

Validierung dieses Stands: alle zwölf bisherigen Testskripte und der neue
DLL-Integrationstest bestanden. Gemeinsamer Starter mit CAMEL-Image und
fragmentierter TCP-Anfrage bestanden. QEMU-Patch rückwärts anwendbar geprüft;
Checkpatch mit `--no-signoff`: null Fehler, ein allgemeiner MAINTAINERS-Hinweis.

CAMEL24-Komplettstart: `python3 tools/zds/f24.py` erzeugt OMF695-Debugdaten, öffnet ZDS II
per `@start.cmd`, lädt das RAM-Debugimage und hält bei `_main` (00039Bh).
Alle zehn Debugansichten werden durch `tools/zds/views.c` geöffnet; Diagnose
`build/f24/views.log`. Vollständiger Nexus-Register-Snapshot zusätzlich getestet;
GET_REGS_ALL-Kompatibilitätsfall `R16=16` abgefangen. Sichtbare Konsole über
Terminalstart, UART-Ein-/Ausgabe im Starter integriert.

## Erweiterte Opcodes (28.10.2026)

168 neue Opcode-Encodings: alle fehlenden direkten Basisbytes, ED-Erweiterungen,
IXH/IXL/IYH/IYL, IN/OUT, alle 28 Block-I/O-Varianten, DAA/NEG/CCF/RLD/RRD/TST,
RST/RETN und CPU-SLP. ED31/ED37-Zielregister vertauscht korrigiert.
Tests: `tests/test_extended_opcodes.py` (195 ROM-Szenarien, 60.000 BCD-Fälle,
13 Negativfälle), zusätzliche IRQ-/SLP-Proben in `tests/test_timer_irq.py`.
113 Encodings durch `examples/extended_opcodes/build.py` mit ZDS bestätigt.
Quellen/Flagwiderspruch LD HL,I und Modellgrenzen: [extended-opcodes.md](extended-opcodes.md).

Alle sieben Opcode-Maps aus UM0077 durch `tests/test_opcode_maps.py` für beide
ADL-Modi abgeglichen. DD/FD76 sind jetzt korrekt ungültig; Indexräume jeweils
95 direkte Encodings plus CB-Dispatcher. Die alte C-Startup-Testprobe enthielt
beim ED31/ED37-Laden dieselbe vertauschte Zuordnung und wurde anhand des
unabhängigen ZDS-Assembler-Ergebnisses korrigiert.

Abschlussvalidierung: alle 15 Testskripte bestanden (einschließlich neuer
Opcode-Map-/Ausführungstests und echter ZDS-II-DLL). ZDS-Assembler bestätigt
113 Encodings. Gesamtpatch gegen unveränderten QEMU-Index sowie rückwärts
gegen den Arbeitsstand geprüft. Checkpatch `--no-signoff`: null Fehler,
nur der allgemeine MAINTAINERS-Hinweis. Neuer CPU-Build unter
`/tmp/qemuez80f91-build-baseline/qemu-system-ez80`; laufende ältere Instanzen
übernehmen ihn erst beim nächsten Start von `python3 tools/zds/f24.py`.

## Ethernet-MAC (2026-10-28)

Neues Gerät `qemu/hw/ez80/emac.c`, Boardverdrahtung zu IRQ-Quellen 0/1/2,
Memory-Hilfsinterface `include/hw/ez80/ez80f91.h`. Direkter Zugriff auf dasselbe
8-KiB-ERAM wie die CPU; RAM_ADDR_U und ERAM_EN werden berücksichtigt.
TX/RX-Deskriptoren, Backend, Filter, CRC/Padding, Ring-Wrap/Overrun,
PHY-Management und PTMR-Polling sind funktional. Startoption `--nic` in
`tools/zds/f24.py`, standardmäßig `none`. Details/Grenzen: `docs/emac.md`.
Test: `tests/test_emac.py` (echte Socketframes und vier Gast-IRQ-Proben).
Noch kein vollständiger ZTP-Netzwerkstack getestet, kein Slirp im Minimalbuild.

## Originales ZTP-TCPUDPDemo (2026-10-28)

`examples/ztp_tcpudp/build.py` baut die lokal installierten 23 Samplequellen
mit originalen Bibliotheken. Produkte nur in `build/ztp-tcpudp` (ignoriert),
keine Herstellerquellen ins Projekt übernehmen. Build warnungsfrei, 188039 Bytes.
RAM-Startparameter an vorhandenes QEMU-Profil angepasst, Oszillator 5 MHz,
AMD-PHY-Adresse 31. `probe.py` zeichnet CPU/MAC/UART und Socketframes auf.
RZK-Scheduler deckte veraltetes oberes Byte bei MLT auf; Produkt nun auf 16 Bit
begrenzt. 15 Regressionstestprogramme bestehen. Hardwarevergleich des oberen
MLT-Bytes fehlt (Nexus-Simulator-Core konnte nicht geladen werden).
Aktueller Stop: IFL_EraseInfoPage, PC 025BA0h–025BA5h, FCh=80h/FFh=02h,
FFh-Port unimplementiert liest FFh und bleibt busy. MAC noch im Reset, kein
TCP-/UDP-Erfolg. Nächste Arbeiten: Flash-Informationsseite/Controller und
UART0-IRQs, dann DHCP-Testpeer. Details: `docs/ztp-tcpudp.md`.

## ZTP TCP/UDP erfolgreich, Flash-Info und UART0 (2026-10-28)

Frühere Flash-Wartegrenze oben ist behoben: `memory.c` implementiert die
512-Byte-Info-Seite, F5h–FFh inklusive Key/Status und Flash-IRQ Quelle 4 (50h).
Hauptarray-Program/Erase melden expliziten Fehler; weiterhin keine volle
Flash-Emulation. Info-Inhalt bleibt über Systemreset, nicht Prozessneustart.
`uart.c`: 16-Byte-RX-FIFO, Trigger/Timeout, Overrun, Loopback, TX/RX/TC-IRQs,
IRQ-Quelle 12 (70h), RX-Timeout aus SCLK. TX synchron, keine Modemflanken.
8 neue Gastproben in `tests/test_flash_uart.py`; alle 16 lokalen Testprogramme
bestehen. Details: `docs/flash-uart.md`.

Originales TCPUDPDemo mit originalem Kernel/UART/MAC/Stack: DHCP OK und IP
172.16.6.186. Externe Flash-Volume-Konfiguration hängt noch beim EXTF-Formatieren.
Separate Buildoption `--filesystem ram` wählt den vorhandenen Hersteller-RAM-
Treiber über zwei ZFS-Konfigurationsdefines in der Buildkopie. Original bleibt
unverändert. RAM-Image 187794 Bytes. UART-Login und originale Befehle
bsdudpserver/bsdtcpserver erfolgreich: 1000 Byte UDP und 4000 Byte TCP bytegenau
über den Socketpeer. TCP-Prüfsummen/Handshake geprüft. Repro:
`python3 examples/ztp_tcpudp/build.py --filesystem ram --out build/ztp-tcpudp-ram`
`python3 examples/ztp_tcpudp/probe.py --out build/ztp-tcpudp-ram --seconds 15 --tcp-test --expect-dhcp`
Probe nutzt deterministisches icount shift=5,sleep=off, da Timer unter der
Host-Wanduhr den langsamen Interpreter sonst verdrängen. Lokaler Peer unter
`examples/ztp_tcpudp/peer.py`, keine Netzwerkweiterleitung.
Details und Grenzen: `docs/ztp-tcpudp.md`.

Abschlussprüfung: Alle 16 lokalen Testprogramme und die echte Nexus-DLL-
Integration bestehen (17 insgesamt). Reproduzierbarer QEMU-Patch aktualisiert,
Vorwärts-/Rückwärts-Prüfung erfolgreich; Checkpatch ohne Fehler.

## start.demo (2026-10-28)

Neuer ausführbarer Rootstarter `python3 -m tools.demo`, Implementierung `tools/demo.py`.
Baut fehlendes/ungültiges RAM-Demoimage automatisch, prüft SHA/Profile/SDK-Pfad,
verwendet Startsperre, QEMU und lokalen DHCP/ARP/ICMP-Socketpeer. UART wird im
aufrufenden Terminal bedient (Raw-Modus mit Wiederherstellung), Ctrl+C/Ctrl+]
beenden Starter und Kindprozess. Login und help interaktiv geprüft.
`--test` ruft die komplette DHCP/UDP/TCP-Probe auf; `--prepare-only`,
`--rebuild`, `--seconds`, `--qemu`, `--zds`, `--out` vorhanden. Keine ZDS-GUI
und keine Hostnetz-Weiterleitung in diesem Starter. Anleitung: docs/ztp-tcpudp.md.

## DHCP immer nadibox (2026-10-28, ersetzt die lokale Peer-Konfiguration)

Benutzervorgabe: DHCP-Server soll immer nadibox sein. `start.demo` und die
Diagnoseprobe verwenden jetzt ausschließlich die reale Bridge br0 und den
vorhandenen /usr/libexec/qemu-bridge-helper (allow br0 vorhanden). Kein eigener
DHCP-Server mehr, auch nicht bei --test; alter peer.py-DHCP-Simulator entfernt.
Nadibox 192.168.77.1 vergibt erfolgreich 192.168.77.16 an 00:90:23:00:01:01.
Host br0=192.168.77.3; enp0s25/enp6s0 sind Bridgeports. Hostkonfiguration
unverändert. QEMU startet pausiert, bis der neue TAP-Port STP-forwarding hat;
sonst wurde der erste Discover vor Ablauf der STP-Wartezeit verworfen.
DHCP-ACK-Server-ID wird geprüft; fremder Server führt zum Abbruch. Neue
Werkzeuge in tools/demo_network.py für PCAP-Leaseauswertung, Bridge-Warten und
Echo-Tests über echte Host-Sockets. --test: DHCP(nadibox)+1000 Byte UDP+4000
Byte TCP erfolgreich. Die alten Hinweise oben auf 172.16.6.x/isolierten DHCP-
Peer sind historisch und nicht mehr die aktuelle Konfiguration.

## Dynamische CS0–CS3 (2026-10-28)

Feste low/high-SRAM-Ausschnitte in memory.c durch vier unabhängige Bänke mit
registergesteuerten Fenstern ersetzt. EN/IO/LBR/UBR sofort wirksam, Priorität
interner RAM > interner Flash > CS0 > CS1 > CS2 > CS3. Unbestücktes `none`
blockiert bei aktivem CS niedrigere CS trotzdem. RAM-Backing 16 MiB pro Bank,
Fenster ab Offset0, Inhalt bleibt über Remap/Resize/Disable/Reset.
Boardoptionen cs0..cs3=ram|flash|none; Standard Flash/RAM/RAM/RAM. Typ bleibt
nach Maschineninitialisierung fest. Starter und Probe bieten --cs0..--cs3.
Flash verwendet QEMU pflash_cfi02, 1 MiB AMD Bottom Boot IDs01/37 (AM29LV008BB-
Geometrie), 16-MiB-Spiegelbereich; neuer öffentlicher Getter fürs Initialisieren
der gelöschten FFh-Zellen. Kconfig wählt PFLASH_CFI02. Keine Datei-Persistenz.

RAM-Debugprofil CS0 jetzt initial deaktiviert: Original-ZDS-Startup schreibt
LBR vor CTL, was bei vorher aktiver CS0-Flashbank kurz den laufenden SRAM-Code
überlagert hat. Siliziumreset bleibt CS0 aktiv00..FF/E8.
13 neue Ausführungsproben in tests/test_chip_selects.py; alter memory-Test
für echte Bank-Relokation statt absolutem Fenster-Crop angepasst. 17 lokale
Testprogramme plus echte Nexus-DLL bestehen (18 insgesamt). ZTP-RAM-Demo mit
nadibox-DHCP und echtem UDP/TCP bleibt erfolgreich. Vollständiger ZFS-Lauf auf
CS0-Flash noch kein Referenztest; vorhandene SDK-Linkervorlage deaktiviert CS0.
Details: docs/chip-selects.md.

## 28.10.2026 – nativer Debugport und Scan Device

QEMU akzeptiert --dbgport=4040 (auch mit getrenntem Argument); aktiviert
TCP Smart Cable auf allen IPv4-Adressen und SDK-Discovery UDP3000 automatisch.
--scan-dev ist explizit möglich, allein jedoch ein Fehler. -S hält CPU an;
ohne -S bleibt Autostart erhalten. Nicht zusammen mit -gdb/-s verwenden.
Hilfsprozess per Python3 mit privatem GDB-Unixsocket; QEMU verwaltet dessen
Lebensdauer. Linux getestet. Bundled Helper liegt in pc-bios/ez80-zds und wird
installiert; kanonische Dateien tools/zds/{ethernet,dtl,rsp,zdi}.py müssen mit
der Bundlekopie bytegleich bleiben (test_dbgport prüft das).

start.f24 verwendet nun den nativen Dienst, Port1234 wird nicht benötigt.
start.demo --dbgport=4040 wartet nach Bridgefreigabe auf ZDS Run; DHCP bleibt
nadibox. Debugger-IP ist Host192.168.77.3, nicht die Gast-IP.

Validiert: alle 18 lokalen test_*.py außer dem separat ausgeführten Wine-Test;
originales SDK escscan.exe findet QEMU; test_zds_ethernet.py --native --sdk-scan
besteht mit originaler nxEz80EthernetSC.dll, Register/RAM/Step/Break/Run/Stop
und unabhängiger QMP-Prüfung. start.demo --dbgport=4040 --seconds 2 startet
mit br0, wartet auf Run und beendet sich sauber. start.f24 --prepare-only
besteht. Neuer GUI-Durchlauf nach Starterumstellung noch nicht ausgeführt.
Patch regeneriert, Vorwärtsprüfung gegen Index und Rückwärtsprüfung gegen
Arbeitsbaum erfolgreich; Checkpatch 0 Fehler, nur MAINTAINERS-Hinweis.
