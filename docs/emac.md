# eZ80F91 Ethernet-MAC

Der integrierte EMAC ist in beiden Maschinenprofilen als `ez80f91-emac`
vorhanden. Er verbindet die I/O-Register 0020h–0059h und das gemeinsame
8-KiB-Ethernet-RAM mit einem QEMU-Netzwerkbackend. Grundlage ist die lokale
Zilog-Produktspezifikation PS019217-1222, Kapitel Ethernet MAC, Seiten 287–333.
Die Implementierung enthält keinen übernommenen ZTP-Treibercode.

## Anschließen

Beim nächsten Start mit ZDS II lässt sich ein Backend angeben:

```sh
python3 tools/zds/f24.py --nic 'socket,connect=127.0.0.1:5555'
```

Vorher muss auf Port 5555 ein QEMU-kompatibler Ethernet-Socket-Peer lauschen.
Alternativ startet QEMU den Listener selbst:

```sh
python3 tools/zds/f24.py --nic 'socket,listen=127.0.0.1:5555'
```

Dasselbe funktioniert beim direkten QEMU-Aufruf, zusätzlich zu den bisherigen
Maschinen-/Image-/UART-Optionen:

```sh
-nic socket,connect=127.0.0.1:5555,model=ez80f91-emac
```

Das Streamprotokoll verwendet pro Ethernetframe eine 4-Byte-Längenangabe in
Netzwerkbytefolge, danach den Frame ohne Präambel und FCS. Ein normaler
TCP-Echo-Dienst ist dafür kein geeigneter Netzwerkpeer. Andere QEMU-Backends
sind über `--nic` ebenfalls wählbar, soweit der jeweilige QEMU-Build sie enthält.
Der aktuelle Minimalbuild enthält kein Slirp; `--nic user` funktioniert dort
nicht. Der Standardstarter verwendet die vorhandene Bridge `br0` über den
QEMU-Bridge-Helper; die Voraussetzungen stehen in [Erste Schritte](getting-started.md).

Standard des Starters ist `--nic none`: Register und RAM bleiben vorhanden,
der PHY meldet ohne Peer keinen Link. Der bisherige Ethernet-ZDI-Kanal auf
4040 und die UART-Konsole auf 4444 arbeiten unabhängig vom Gast-MAC.
CAMEL24 enthält durch diese Erweiterung noch keinen Ethernettreiber oder
TCP/IP-Stack. Der originale ZTP-Stack ist inzwischen mit DHCP und TCP/UDP-Echo geprüft:
[TCPUDPDemo und dessen RAM-Dateisystem-Konfiguration](ztp-tcpudp.md).

## Gastseitige Verwendung

1. EMAC_RST auf 3Fh setzen, Grenzen und Software-RRP programmieren.
2. TX-Ring `[TLBP, BP)` und RX-Ring `[BP, RHBP)` im Ethernet-RAM aufteilen.
   RHBP=0 bezeichnet dessen Ende bei Offset 2000h. Pointerregister sind
   32-Byte-ausgerichtete Offsets; BUFSZ wählt 256/128/64/32-Byte-Blöcke.
3. STAD0–5 in Netzwerkbytefolge, CFG1, CFG4.RXEN und AFR setzen.
4. Resetbits freigeben und nach Bedarf IEN setzen.
5. TX-Deskriptoren und Payload schreiben, Ownership zuletzt setzen; PTMR
   schreiben. Auch PTMR=0 prüft einmal den aktuellen Deskriptor, ohne weiter
   periodisch zu pollen. Ein Wert größer null pollt alle `256 * PTMR`
   Systemtakte nach weiteren freigegebenen Deskriptoren.
6. RX-Deskriptoren abarbeiten, RRP nachführen und ISTAT-Bits mit Eins quittieren.

Ein Deskriptor besteht aus 7 Bytes: 24-Bit-NP, 16-Bit-Paketlänge und
16-Bit-Status, jeweils Little Endian. NP ist eine vollständige CPU-Adresse,
kein Offset. Der Frame beginnt unmittelbar bei Offset 7. TX verarbeitet nur
Deskriptoren mit Statusbit 15; bei Abschluss wird die Ownership gelöscht.
Die Pointer bleiben innerhalb ihrer Partition; Payload kann am Ringende
umbrechen. Ungültige TX-Zeiger führen zu TxFSMERR und erfordern TX-Reset.

Mit CFG1.CRCEN wird TX-Pkt_Size als Anzahl der gelieferten Framebytes ohne
FCS verwendet, entsprechend der Nutzung durch den installierten F91-Treiber.
Ohne CRCEN muss der Gast eine gültige FCS mitliefern. Ungültige FCS führt zum
abgebrochenen TX-Deskriptor statt zu einem fehlerhaften Frame am Backend.
PADEN zusammen mit CRCEN ergänzt kurze TX-Frames auf 60 Bytes ohne FCS.
RX-Pkt_Size enthält die vier im Ethernet-RAM angehängten FCS-Bytes.

RX reserviert einen Block zur Unterscheidung zwischen leerem und vollem Ring.
Bei Platzmangel erhält der reservierte Block einen abschließenden Deskriptor
mit RxOVR und ohne RxOK; RXDONE und RX_OVR werden gesetzt. So erkennt auch
der originale Zilog-Treiber ohne separat aktivierten Überlaufinterrupt den
Fehler und quittiert RX_OVR beim Abarbeiten dieses Deskriptors. Weitere
Frames werden bis zur expliziten Quittierung verworfen. ERAM_EN und RAM_ADDR_U gelten auch für den MAC-Zugriff;
BP_U ist ein schreibgeschützter Spiegel von RAM_ADDR_U.

Unterstützt sind Stationsadresse, Broadcast, Promiscuous, alle Multicasts und
64-Bit-Multicast-Hashfilter. MAC- und PHY-Loopback sind funktional vorhanden.
Die drei Interruptklassen sind mit den F91-Vektoren 40h (RX), 44h (TX) und
48h (System) verbunden. ISTAT ist sticky und W1C, IEN maskiert die Leitungen.

Der funktionale Clause-22-PHY liegt standardmäßig an Adresse 0 und meldet
IDs 0022h/561Bh. Unterstützt werden Management-Lese-/Schreibzugriff, BMCR-
Reset, Powerdown/Isolation, Linkstatus des Backends und MGTDONE. Die
Konfigurationsproperty `phy-addr` erlaubt Adressen 0–31.

## Geprüft und Grenzen

```sh
python3 tests/test_emac.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
```

Der Test prüft echte Socket-TX/RX-Frames, Deskriptoren und FCS, Padding,
CRC-Abbruch, Filter einschließlich Multicast-Hash, TX- und RX-Wrap, RX-Overrun
mit Wiederanlauf, ungültige Zeiger, RAM-Relokation/Enable und PHY-Linkwechsel.
Laufender eZ80-Gastcode prüft alle drei IM2-Interruptklassen und periodisches
TX-Polling. Die übrigen CPU-, CAMEL-, PLL-, Timer- und FreeRTOS-Tests bestehen
mit eingebautem MAC weiter.

Dies ist ein funktionales Paketmodell: keine PHY-Wellenformen oder reale
10/100-Mbit-Übertragungszeit, keine Kollisionen/Backoff, keine Pause-/Jam-
Flusssteuerung, kein FIFO-Testbetrieb, keine proprietären Header und keine
vollständige 802.3-Längen-/Fehlerklassifizierung. Fehlerhafte Frames vom
Backend werden nicht als PHY-Fehler simuliert. VLAN-Tags werden unverändert
transportiert und beim Empfang markiert; spezielles VLAN-Padding fehlt.
MII-Einzelzugriffe schließen synchron ab. SCAN aktualisiert beim Lesen von
PRSD; SCINC, zeitgesteuertes Scanning, Busy-Timing und Link-Latch-Low fehlen.
Herstellerspezifische PHY-Funktionen und eine vollständige Auto-Negotiation
werden nicht simuliert. Migration/Snapshots des Gerätezustands fehlen.
