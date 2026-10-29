# Flash-Informationsseite und UART0

Die eZ80F91-Emulation unterstützt jetzt die Flash-Informationsseite und die
UART0-Interruptpfade, die das originale ZTP-TCPUDPDemo benötigt. Grundlage
sind die Flash- und UART-Kapitel der lokalen Zilog-Produktspezifikation
PS019217-1222.

## Flash

Die Register F5h–FFh werden vom Speichergerät bereitgestellt. Die separate
512-Byte-Informationsseite startet bei einer neuen QEMU-Instanz mit FFh und
bleibt über `system_reset` erhalten. Sie ist ausschließlich über FLASH_DATA
(F6h) mit INFO_EN in FLASH_PAGE zugänglich, unabhängig vom CPU-Flashmapping.

Unterstützt sind Byteprogrammierung mit NOR-Verhalten (nur 1→0), Lesen,
Adressfortschaltung über Spalten-/Zeilenende, Page Erase der Informationsseite
und Row-Program-Abschluss am Zeilenende. Die Erase-Bits löschen sich selbst.
DONE und Fehlerstatus werden über FLASH_IRQ bereitgestellt; Statuslesen
quittiert sie. DONE_IEN/ERR_IEN steuern die Interruptquelle mit Vektor 50h.
Die B6h/49h-Schlüsselfolge entsperrt FLASH_FDIV und FLASH_PROT bis zum nächsten
Schreiben eines dieser beiden Register.

Das 256-KiB-Hauptarray unterstützt NOR-Byteprogrammierung über Speicherzugriffe
und FLASH_DATA, 2-KiB-Page-Erase und Mass-Erase. Die acht FLASH_PROT-Bits
schützen jeweils 32 KiB; geschützte Schreib-/Löschzugriffe melden
WR_VIO/PG_VIO/MASS_VIO. Ein erfolgreicher Erase setzt DONE, wodurch der
originale ZDS-RAM-Loader seine Pollschleife verlassen kann. Mass-Erase löscht
die Informationsseite nur mit INFO_EN; Page-Erase mit INFO_EN löscht nur diese.

Dies ist eine funktionale Teilimplementierung: Erase schließt synchron ab,
es gibt keine echten Wartezeiten und keine Row-Program-Zeitüberschreitung.
Die Informationsseite hat noch keine Persistenzdatei über QEMU-Neustarts.
Die Schlüsselfolge wird innerhalb der Flash-Register geprüft;
intervenierende I/O-Schreibzugriffe auf andere Geräte werden dafür noch nicht
erfasst. Der externe WP-Pin wird nicht separat modelliert.

## UART0

UART0 besitzt einen 16-Byte-Empfangspuffer im FIFO-Modus, RX-Triggerlevel
1/4/8/14 und einen Empfangs-Timeout nach vier Zeichenzeiten. Dieser verwendet
die aktuelle SCLK-Quelle und den Baudteiler; das 1,5-Stopbit-Format wird dabei
mit zwei Stopbits angenähert. Ohne FIFO steht ein Empfangsbyte bereit.

RX, Empfangs-Timeout, Overrun/Line-Status, THRE und Transmission Complete
werden über IIR/IER und die Interruptquelle mit Vektor 70h bedient. RX hat
Vorrang vor TX; Overrun wird durch Lesen von LSR quittiert. IIR-Lesen quittiert
den THRE-Latch. FIFO-Reset, DLAB, Scratchpad und die bestehende GPIO-/PPD-
Freigabe bleiben wirksam. Interner Loopback ist für RX/TX vorhanden.

TX wird weiterhin unmittelbar an das Zeichenbackend übergeben: Es gibt keinen
zeitlich gefüllten TX-FIFO oder realen Schieberegisterablauf. Ein verbundenes
Streambackend gilt als bereit (CTS/DSR/DCD); Modemflanken und ihre Interrupts
werden nicht simuliert. Paritäts-/Framing-/Breakfehler und Multidrop fehlen.
Clock-/Formatwechsel während eines laufenden Timeouts sind nicht zyklusgenau.

## Prüfung

```sh
python3 tests/test_flash_uart.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
```

Acht Gasttests prüfen NOR-Programmierung und Reset-Erhalt, Adress-Wrap und
Erase, Row-DONE, Register-Unlock/Relock, explizite Hauptarray-Ablehnung,
Flash-IM2-Interrupt, UART-Puffer/Loopback/Quittierung, Empfangs-Timeout und
Overrun sowie RX-/TX-IM2-Interrupts. Zusätzlich laufen die originalen ZTP-
Treiber im [TCP/UDP-Demo](ztp-tcpudp.md).

## Flash-Dateien

QEMU lädt beim Start ausschließlich das interne Flash (256 KiB). Externe
Flashs (je 1 MiB) bleiben zunächst mit `FF` gefüllt und ohne Dateianbindung.
Erst wenn die Firmware nach dem Setzen der Grenzen das CS-Steuerregister
mit einem gültigen, aktivierten Speicherfenster schreibt, wird die Datei für
die tatsächliche untere Basisadresse geladen. Reset allein lädt keine externe
Datei. Erneutes Aktivieren derselben Adresse erhält den aktuellen Inhalt;
Aktivieren mit einer neuen Basis speichert die bisherige Datei und lädt die neue.

Die Rohdateien liegen im aktuellen Arbeitsverzeichnis:
`ez80f91_<BASISADDR>.<DEBUGPORT>`, hexadezimale Adresse in Großbuchstaben ohne
führende Nullen. Internes Flash verwendet `0`; ohne `--dbgport` ist die
Endung `.0`. Es gibt keine fest vorgegebenen externen Dateiadressen.
Beim regulären Beenden (auch SIGINT/SIGTERM) werden das interne und alle
bereits angebundenen externen Flashs gespeichert. Gleiche Dateiadressen
mehrerer Flashs werden abgewiesen.

Fehlende Dateien und das Ende kürzerer Dateien werden mit `FF` gefüllt.
Zu große oder nicht lesbare Dateien führen zu einem Startfehler. `-bios`
überschreibt den entsprechenden Anfang des geladenen internen Flashs;
ohne `-bios` startet QEMU mit dem gespeicherten Inhalt. `-kernel` für
RAM-Boot bleibt verfügbar. Die Information-Page bleibt hiervon unabhängig;
Programmieren und Löschen des Hauptarrays sind funktional implementiert. SIGKILL oder ein Prozessabsturz können nicht mehr gespeichert werden.

```sh
python3 tests/test_flash_persistence.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
```

Der ZDS-Erase-Wartecode und RAM-basiertes Programmieren werden zusätzlich geprüft:

```sh
python3 tests/test_internal_flash.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
```
