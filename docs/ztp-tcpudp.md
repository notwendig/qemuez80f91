# Originales ZTP 2.5.1 TCPUDPDemo

Das lokal installierte TCPUDPDemo läuft mit dem originalen RZK-Kernel,
UART-/MAC-Treiber und ZTP-Netzwerkstack. Nachgewiesen sind DHCP, Shell-Login
über UART, ein bytegenaues UDP-Echo mit 1000 Bytes und ein bytegenaues TCP-Echo
mit 4000 Bytes über echte Host-Sockets. DHCP-Server ist immer
**nadibox (192.168.77.1)**; es gibt keinen eingebauten DHCP-Ersatzserver.
Beim Test vergab die nadibox die Gastadresse **192.168.77.16**. Diese Adresse
kommt aus der DHCP-Lease und wird im Starter nicht fest eingestellt.

Für den vollständigen Test wird das vom Hersteller bereits vorgesehene
RAM-Dateisystem gewählt. Externer AMD-Flash ist inzwischen über die
[dynamischen Chip-Selects](chip-selects.md) verfügbar. Die ursprüngliche
SDK-RAM-Linkervorlage deaktiviert jedoch CS0; ein vollständiger ZFS-Flash-Start
mit angepasster Freigabe ist noch nicht als Referenztest übernommen.

## Mit App-Konsole starten

```sh
python3 -m tools.demo
```

Der Starter baut das RAM-Testimage bei Bedarf und verbindet QEMU über den
vorhandenen QEMU-Bridge-Helper mit `br0`. Die UART-Konsole läuft im aufrufenden
Terminal. Anmeldung:
`anonymous` / `anonymous`. Danach stehen `help`, `bsdudpserver` und
`bsdtcpserver` zur Verfügung. Beenden mit Strg+C oder Strg+]; der Starter
beendet QEMU und stellt den Terminalmodus wieder her.

```sh
python3 -m tools.demo --test           # DHCP + 1000 Byte UDP + 4000 Byte TCP automatisch
python3 -m tools.demo --rebuild        # neu übersetzen und Konsole starten
python3 -m tools.demo --prepare-only   # nur Image vorbereiten
python3 -m tools.demo --seconds 20     # Konsole nach 20 Sekunden schließen
```

`--qemu`, `--zds` und `--out` wählen Emulator, Toolchain und Buildverzeichnis;
QEMU_EZ80 und ZDS_HOME werden ebenfalls berücksichtigt. Eine Startsperre
verhindert parallele Starter im selben Ausgabeverzeichnis. `--bridge` wählt
die Bridge, `--bridge-helper` den vorhandenen Helper und `--dhcp-server`
die erwartete IPv4-Adresse der nadibox (Standard 192.168.77.1).

Der Host ist mit 192.168.77.3 an br0 angeschlossen; dessen physische Ports sind
enp0s25 und enp6s0. Der vorhandene Helper `/usr/libexec/qemu-bridge-helper` ist
für br0 freigegeben. Der Starter ändert keine Host-Netzkonfiguration. Er lässt
den Gast zunächst pausiert, bis der neue TAP-Port den STP-Zustand „forwarding“
erreicht. Dadurch geht der erste DHCP-Discover nicht während der Bridge-
Anlaufzeit verloren. Nach dem Beenden wird der temporäre TAP-Port geschlossen.

DHCP-ACKs werden aus dem Mitschnitt ausgewertet. Ein ACK für die Gast-MAC
00:90:23:00:01:01 von einer anderen Serveradresse führt zum Abbruch; es gibt
keinen Rückfall auf einen lokalen Server. Der Gast ist im echten LAN erreichbar.
`--test` verwendet dieselbe Bridge und prüft die Echo-Dienste vom Host mit
normalen UDP-/TCP-Sockets. ZDS II wird von diesem Starter nicht geöffnet.

Diagnose im Ausgabeverzeichnis: `uart.log`, `qemu.log`, `devices.log`,
`network.pcap` und `network.json`. Letzteres enthält DHCP-Server und zugewiesene
Gastadresse; im Test zusätzlich `dhcp_verified`, `udp_echo_ok`, `tcp_echo_ok`.

## Vollständigen Test reproduzieren

```sh
python3 examples/ztp_tcpudp/build.py --filesystem ram --out build/ztp-tcpudp-ram
python3 examples/ztp_tcpudp/probe.py --out build/ztp-tcpudp-ram --seconds 30 --tcp-test --expect-dhcp
```

Der Builder verwendet die lokale Installation unter
`~/.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5` und deren Projekt
`ZTP2.5.1/ZTP/SamplePrograms/TCPUDPDemo/ZTP_TCPUDP_DEMO_eZ80F91_99C0879-AMD.zdsproj`.
Eine andere Installation kann mit `--zds` gewählt werden. Die 23 Projektquellen
werden mit den Defines und Bibliotheken des Samples übersetzt. Der Wine-
Batchlauf und der Linker liefern HEX, OMF695, Mapdatei und Rohimage.

Die installierten Dateien bleiben unverändert. Herstellerquellen und
Bibliotheksprodukte liegen ausschließlich im ignorierten `build/`-Verzeichnis
und werden nicht mit dem Emulator verteilt. In der RAM-Variante werden nur die
beiden vorgesehenen ZFS_USES_XFL/ZFS_USES_RAM-Schalter in der Buildkopie von
ZFS_Conf.c gewechselt. Das RAM-Volume liegt im internen RAM bei B7F000h–B7FFFFh;
Anwendung und Threadstacks liegen im externen SRAM. Netzwerkcode, Shell,
Socket-Demo-Funktionen und Bibliotheken werden nicht ersetzt.

Der warnungsfreie RAM-Build erzeugte ein 187794-Byte-Rohimage und belegte
111578 Bytes im Anwendungs-RAM. Der originale Flash-Dateisystem-Build erzeugte
188039 Bytes und belegte 114762 Bytes im Anwendungs-RAM.

Auch die Diagnoseprobe verbindet sich mit br0 und verwendet ausschließlich
DHCP von der nadibox. `--tcp-test` führt zuerst den UDP-Test aus und bedient
dann den TCP-Server. Über die UART werden die im Sample vorgegebenen
Loginwerte `anonymous`/`anonymous`, die Befehle `bsdudpserver`/`bsdtcpserver`
und die Ports 4000/4001 eingegeben. Der Test wartet nach dem ersten Shellprompt
kurz, damit der Anwendungsthread seine zusätzlichen Befehle registrieren kann.
Die Gegenstellen laufen als normale Host-Sockets; die erwartete Gastadresse
wird aus dem DHCP-ACK der nadibox gelesen.

`--udp-test` prüft nur UDP. Ohne diese Optionen wird die UART protokolliert,
aber nicht automatisch bedient. `--expect-dhcp` verlangt die Meldung „DHCP OK“
und ein passendes ACK der nadibox. `--dhcp` bleibt als kompatibler Aufrufparameter
erhalten und startet keinen eigenen Server. Die frühere Simulation mit
172.16.6.1 ist entfernt.

Die Probe speichert zusätzlich `probe.json` mit CPU-/MAC-Schnappschüssen,
DHCP-Leases und Testergebnissen. Vollständige Frames stehen in `network.pcap`.
Das sind Funktionstests einzelner Verbindungen, keine Lasttests.

## Originale Flash-Konfiguration separat prüfen

```sh
python3 examples/ztp_tcpudp/build.py
python3 examples/ztp_tcpudp/probe.py --seconds 30 --expect-dhcp
```

Diese Variante erreicht die Meldungen „DHCP OK“ und „Initializing network
stack“, danach „Formatting the Invalid Volume : EXTF“. Der Linkerrahmen
setzt CS0_CTL=0; die externe Flash-Bank benötigt eine passende Freigabe. Die Flash-Informationsseite für persistente ZTP-
Konfiguration ist dagegen implementiert; sie überlebt einen QEMU-Systemreset,
aber keinen neuen QEMU-Prozess. [Flash- und UART-Funktionsumfang](flash-uart.md).

## Startprofil und historische Fehler

Der Linkerrahmen stammt aus dem lokal vorhandenen ZTPDemo-RAM-Build. Für QEMU
werden CS1 auf den unteren SRAM-Bereich, CS2 auf den oberen SRAM-Bereich und
FLASH_CTL auf 60h gesetzt. Damit bleibt das RAM-Image beim originalen Startup
sichtbar. RAM_ADDR_U=B7h und die 5-MHz-/PLL-Konfiguration bleiben erhalten.
Die Probe verwendet `osc-frequency=5000000` und AMD-PHY-Adresse 31.
`--memory-profile vendor` belässt die Werte der installierten Linkervorlage und
passt nicht zum derzeitigen QEMU-RAM-Profil.

Die Probe verwendet `-icount shift=5,sleep=off`, also eine virtuelle Zeit von
32 ns je Gastinstruktion. Damit verdrängen Echtzeit-Timer den relativ langsamen
Interpreter nicht bei der RZK-Initialisierung. Dies ersetzt keine genaue
CPU-Zyklensimulation. `--icount` erlaubt einen anderen Shift.

Beim ersten Versuch bewahrte MLT ein altes oberes Registerbyte. Der originale
RZK-Scheduler verwendete deshalb einen falschen Tabellenindex und einen
ungültigen Stack. Das Ergebnis wird jetzt auf 16 Bit begrenzt; CPU-Test und
Schedulerpfad sind geprüft. UM0077 beschreibt das 16-Bit-Produkt, aber nicht
eindeutig dessen oberes Byte. Ein unabhängiger Hardwarevergleich fehlt; der
Versuch über nxEz80sim.dll konnte den Simulator-Core nicht laden.

Danach wartete IFL_EraseInfoPage bei FLASH_PGCTL auf einen nicht implementierten
Registerzugriff. Dieser Pfad funktioniert inzwischen mit der emulierten
512-Byte-Informationsseite. UART0-FIFO und Interrupts erlauben die originale
Konsole. Interner Haupt-Flash bleibt hinsichtlich Programmieren/Löschen offen;
der erfolgreiche RAM-Dateisystem-Test benötigt ihn nicht.

Zur Eingrenzung können `--break-at 0x...` und `--trace-steps ...` verwendet
werden. Diagnoseadressen müssen aus der Mapdatei des jeweiligen Builds stammen;
Flash- und RAM-Dateisystemvarianten haben unterschiedliche Adressen.

## ZDS-II-Debugport und Gerätesuche

```sh
python3 -m tools.demo --dbgport=4040
```

Aktiviert Ethernet Smart Cable und Scan Device (UDP 3000). Die CPU wartet
bis zum Run in ZDS II; erst danach startet der Gast einschließlich DHCP bei
nadibox. Debugger-IP ist die Hostadresse (hier `192.168.77.3`), lokal
`127.0.0.1`. Diese Betriebsart ist nicht mit `--test` kombinierbar.
[Debugprotokoll und Grenzen](zds-ethernet.md).
