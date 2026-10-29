# ZDS II über Ethernet Smart Cable / ZDI

QEMU kann über die installierte `nxEz80EthernetSC.dll` angesprochen werden.
Die DLL bleibt unverändert. Grundlage sind `../NexusSDK_1.1`, die installierte
`config/eZ80F91algo.ini` und ein Integrationstest mit der echten PE32-DLL
unter Wine.

## Start

Für den vollständigen CAMEL24-Start einschließlich ZDS II und Debugsymbolen:
`python3 tools/zds/f24.py` — [Anleitung](start-f24.md).

Nach dem QEMU-Build aus [first-execution.md](first-execution.md):

```sh
/tmp/qemuez80f91-build-baseline/qemu-system-ez80 \
  -M ez80f91-freertos,ram-boot=on -kernel examples/camelf91/camel.bin \
  --dbgport=4040 --scan-dev -S -display none -monitor none -serial stdio -nic none
```

`--dbgport=4040` startet den TCP-Debugdienst und aktiviert automatisch
**Scan Device** auf UDP-Port 3000. `--scan-dev` kann zusätzlich angegeben werden.
`-S` hält die CPU bis zum Debugger-Run an; ohne `-S` startet QEMU normal.
Der Dienst bindet an alle IPv4-Schnittstellen. Lokal ist die Debugger-IP
`127.0.0.1`, im LAN die Hostadresse, hier `192.168.77.3`.
Die vom Gast über nadibox bezogene IP gehört zum Gastnetzwerk und ist davon unabhängig.

QEMU startet einen mitgelieferten Python-3-Hilfsprozess mit privatem GDB-Unixsocket
und beendet ihn beim eigenen Ende. Python 3 muss im Suchpfad liegen.
Ein zusätzlicher `-gdb`-/`-s`-Endpunkt ist mit `--dbgport` nicht kombinierbar.
Der Linux-Pfad ist getestet; Windows-Hosts werden für diese Option abgewiesen.

In ZDS II im Projekt unter **Debugger / Debug Tool** das **Ethernet Smart Cable**
wählen und dessen Einstellungen auf IP **127.0.0.1**, Port **4040** setzen.
Die Installation bezeichnet den Tool-Typ als `EthernetSmartCable`, den
Kommunikationstyp als `ethernetSmartCable`; die Standardwerte stehen in
`config/DefaultDebugTools.xml`. Die bestehende USB-Auswahl im unveränderten
CAMEL-Upstreamprojekt muss entsprechend umgestellt werden.
Alternativ **Scan Device** wählen: Der Adapter erscheint als `QEMU-eZ80F91`.
Das originale SDK sendet `scan` an UDP 3000. Die Antwort lautet
`100,QEMU-eZ80F91,02:5A:44:49:HH:LL,PORT`; HH/LL ergeben sich aus dem
Debugport. Diese synthetische Adapterkennung ist unabhängig vom Gast-MAC.

Für das vorab geladene CAMEL-Image die Debugverbindung zum laufenden Ziel
verwenden. Ein ZDS-Flash-Download/Erase ist bisher nicht unterstützt.
ZDS darf Register und RAM ändern und die CPU starten, anhalten oder schrittweise
fortsetzen. Eine ZDS-Resetsequenz kann Speicher-Mapping und CPU-Startwerte
entsprechend den Projekteinstellungen ändern.

Der GUI-Ablauf für CAMEL24 wurde mit `python3 tools/zds/f24.py` automatisiert geprüft:
Projekt öffnen, Ethernet-Verbindung, OMF695-Download und Halt mit Quellcodeanzeige.
Der untenstehende Test prüft zusätzlich dieselbe installierte Debug-DLL direkt
über die Nexus-API.

## Nachgewiesene Funktionen

```sh
python3 tests/test_zds_ethernet.py --native --sdk-scan
python3 tests/test_dbgport.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
```

Voraussetzungen: `wine`, `i686-w64-mingw32-gcc`, SDK 1.1 sowie ZDS II 5.3.5.
Mit `--sdk`, `--zds`, `--qemu`, `--wine-prefix` sind andere Pfade möglich.
Der Test schreibt ausschließlich temporäre Dateien und verwendet standardmäßig
das separate Wine-Präfix `/tmp/qemuez80f91-zds-wine`.

Geprüft werden Verbindungsaufbau, DLL-Register-Selbsttest, vollständiger
Register-Snapshot für die IDE-Ansichten einschließlich Erhalt von BC, Initialisierung,
Resetsequenz mit Portzugriffen, BC schreiben/lesen, binärer RAM-Transfer an der
RAM-Untergrenze, PC setzen/lesen, Einzelschritt samt Ereignis, Ausführung von
`LD A,42h`, Hardware-Breakpoint samt asynchronem Ereignis, Breakpoint löschen,
freier Lauf, Statusabfrage und Anhalten. Abschließend werden CPU und RAM
unabhängig von der Nexus-DLL direkt in QEMU geprüft. Jeder Fehler ergibt einen
fehlschlagenden Prozessstatus.

## Aufbau und Protokoll

```text
ZDS II / Nexus-API
  → nxEz80EthernetSC.dll
  → TCP 127.0.0.1:4040 (DTL-Algorithmen)
  → tools/zds/ethernet.py + dtl.py + zdi.py
  → privater Unixsocket (GDB Remote)
  → echter QEMU-CPU-/Speicherzustand
```

Anfragen haben einen 3-Byte-Kopf: Gesamtlänge als uint16 LE und Typ 0.
Es folgt ein DTL-Algorithmus mit abschließendem NUL. Binärblöcke stehen als
`[]=<hex-Länge>:` plus Rohbytes im Algorithmus; sie können selbst NUL enthalten.
Antworten verwenden Typ 0, Status `00`, vier hexadezimale Längenzeichen,
hexadezimale Daten und NUL. Der Treiber akzeptiert dieses durch seinen Parser
ermittelte Format. Ein Breakpoint wird durch ein separates Typ-1-Paket mit
Ereignisnummer 0 gemeldet.

DTL enthält Variablen, Register, Rechenausdrücke, Puffer und Schleifen.
Die Brücke interpretiert die für die geprüften eZ80-Abläufe benötigte Teilmenge.
Unbekannte Befehle werden als Fehler zurückgegeben. Firmware-Update, Trace und HALT/SLEEP-Ereignisse
sind nicht implementiert. Die originalen ZDS-Flash-Algorithmen für internes
F91-Flash und externes AMD AM29LV008BB sind geprüft. Injizierte ZDI-Befehle unterstützen die in den
Register- und Portalgorithmen benötigten Opcodes; keine beliebige
Instruction-Store-Ausführung. Die allgemeinen CPU-/Peripheriegrenzen des
Emulators gelten weiterhin. Das ist die Ethernet-Verbindung zum Debugadapter;
der Gast-EMAC verwendet sein eigenes Netzwerkbackend.

Die Header aus SDK 1.1 stimmen nicht vollständig mit der installierten DLL
überein. Der Test verwendet PE32 mit Packung 4; `nx_Control` erwartet den
Vendor-Bereich ab Byte 100. Die DLL 5.3.5 prüft für `initializeTarget` ein
führendes Größenfeld `0x470`, das in den alten Headern auskommentiert ist.
Diese Anpassung ist auf den Testaufruf beschränkt. ZDS II verwendet selbst
seine passende ABI.

## Interner QEMU-Debugzugriff

24 Registerslots mit jeweils 32 Bit Little Endian, in dieser Reihenfolge:

```text
pc bc de hl ix iy bc_shadow de_shadow hl_shadow spl sps i
 a f a_shadow f_shadow r mbase adl madl iff1 iff2 im ei_delay
```

Die Portadressen 0000h–FFFFh sind im privaten Debugfenster
`0x1000000 + Port` les-/schreibbar. Dieser Bereich ist nur im Debugzugriff
vorhanden, nicht im 24-Bit-Adressraum des Gasts. CPU-Einzelschritt und
Breakpoints werden durch QEMUs vorhandenen GDB-/TCG-Pfad ausgeführt.

Alternativer manueller Start zum Diagnostizieren (separate Brücke):

```sh
/tmp/qemuez80f91-build-baseline/qemu-system-ez80 \
  -M ez80f91-freertos,ram-boot=on -kernel examples/camelf91/camel.bin \
  -S -gdb tcp:127.0.0.1:1234 -display none -serial stdio -monitor none
# In einem zweiten Terminal:
python3 tools/zds/ethernet.py --verbose
```

## Flashen mit ZDS II

`./start.sh` startet den Debugdienst mit dem gespeicherten Flash; ZDS II kann
über Ethernet Smart Cable auf `127.0.0.1:4040` verbinden. Der originale Treiber
löscht, programmiert und verifiziert internes F91-Flash und externes AMD
AM29LV008BB über seine unveränderten RAM-Loader. Die Speicher-/Chip-Select-
Einstellungen des ZDS-Targets müssen zur gewünschten Bestückung passen.

Die Brücke meldet bei `GET_EMUL_CONFIG` (`.#$`) die Firmwarekennung und
8192 Byte Transportpuffer. Daraus berechnet die ZDS-DLL sichere Blockgrößen
für ihren auf 8448 Byte begrenzten Empfangspuffer. Eine leere Konfiguration
führte zuvor zu übergroßen Antworten und fehlerhaften RAM-Prüfungen.
ZDI-Blocklesen berücksichtigt den Dummy-Read und den zwei Byte vorauseilenden
PC der Prefetch-Pipeline; dadurch bleiben geteilte Übertragungen lückenlos.
GDB-Schreibzugriffe werden in höchstens 1024 Byte große Blöcke aufgeteilt.

Vollständiger Integrationstest mit der installierten Original-DLL:

```sh
python3 tests/test_zds_flash.py
```

Der Test verwendet eine eigene QEMU-Instanz und einen freien Debugport.
Er prüft Mass-Erase, Programmieren von 10 KiB über mehrere RAM-Blöcke,
mehrteilige Verifikation, Page-Erase mit erhaltenen Nachbarseiten sowie
Löschen/Programmieren/Verifikation des externen AMD-Flashs. Danach werden
die gespeicherten internen und externen Flash-Dateien bytegenau verglichen.
Der 8-KiB-RAM-Arbeitsbereich wird ohne Rückfallwarnung geprüft.
Mit `--qemu`, `--zds`, `--sdk` und `--wine-prefix` sind andere Installationen
wählbar. Ein bereits laufendes QEMU muss nach Änderungen an der Debugbrücke
neu gestartet werden.
