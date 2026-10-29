# eZ80-Kern und eZ80F91: Implementierungsgrundlage

## Verbindliche Quellen

Lokale Herstellerdokumente in `../doc/`:

- `um0077.pdf`: eZ80 CPU User Manual, UM007715-0415.
- `ps0192.pdf`: eZ80F91 MCU Product Specification, PS019217-1222.

Seitenangaben unten bezeichnen gedruckte Seiten, nicht PDF-Seitenzahlen.
Die PDF-Seitenzahl ist in diesen beiden Revisionen jeweils um 9 höher.
Das Ziel ist der F91 MCU nach PS0192. Das ebenfalls vorhandene PS0270
beschreibt den F91 ASSP und wird nicht stillschweigend als Ersatz verwendet.

## Abgrenzung

Der eZ80 ist der CPU-Kern, der eZ80F91 ein konkreter Mikrocontroller mit
integriertem eZ80-Kern. F91 ist keine alternative Betriebsart des Kerns.
Ein gewöhnlicher Z80-Interpreter genügt nicht.

| Bereich | CPU-Kern | F91-SoC / virtuelle Platine |
| --- | --- | --- |
| Ausführung | Register, ALU, Decoder, Flags, Präfixe | CPU-Variante und Taktkonfiguration |
| Adressierung | Z80-Modus, ADL, MBASE, SPS/SPL | Speicherdekodierung und Remapping |
| Interrupts | Annahme, Stack, Moduswechsel, Rückkehr | Quellen, Prioritäten, Vektorbereitstellung |
| Speicher | Speicher- und I/O-Zugriffe ausführen | Flash, RAM, Chip Selects, Wait States |
| Geräte | Keine UART-Register im CPU-Decoder | UART, GPIO, Timer, EMAC, weitere Geräte |

UM0077 S. 6–18 beschreibt Z80-/ADL-Modus, Register und Moduswechsel.
Z80-Modus ist der Resetmodus; 16-Bit-Speicheradressen erhalten MBASE als
oberes Byte. ADL erlaubt 24-Bit-Adressen und Register. SPS und SPL sowie
die Präfixe .SIS/.SIL/.LIS/.LIL müssen explizit modelliert werden.
Assemblerdirektiven wie `.ASSUME ADL=1` ändern keinen Hardwarezustand.

### F91-Eigenschaften des CPU-Modells

PS0192 S. 39 nennt einen 16-Bit-Interruptvektor und die Befehle
`LD I,HL` (ED C7) sowie `LD HL,I` (ED D7). UM0077 S. 195 und 200
bestätigt, dass diese Befehle bei eZ80190, eZ80L92 und eZ80F92/F93
nicht unterstützt werden. Das F91-Modell benötigt daher einen 16-Bit-I-Zustand;
eine pauschale Übernahme beliebiger eZ80-Varianten ist ungeeignet.

Offener Dokumentwiderspruch: Die Übersicht UM0077 S. 66 kennzeichnet
`LD HL,I` ohne Flagänderungen, die Einzelbeschreibung S. 195 nennt
S/Z/H/PV/N-Änderungen bei unverändertem C. Vor Implementierung dieses
Befehls sind unabhängige Referenz oder Hardwaretest erforderlich.
Für den ersten UART-Test wird dieser Befehl nicht benötigt.

## Reset und Speicher

PS0192 S. 41: Systemreset setzt PC auf 0x000000 und GPIO auf Eingänge.
Resetquellen umfassen POR, Brownout, externes RESET, entsprechend
konfigurierten Watchdog, RTC-Weckreset aus SLEEP und Debug-Reset.
Der Resetcontroller beschreibt 1025 SCLK-Zyklen; elektrische und
zeitliche Genauigkeit gehört noch nicht zur ersten funktionalen Ausbaustufe.
Andere CPU-Register werden nicht ohne Beleg als null initialisiert.

| Ressource | Resetabbild / Wert | Quelle PS0192 |
| --- | --- | --- |
| Programm-Flash, 256 KiB | 0x000000–0x03FFFF, aktiviert | S. 104–105, Tabellen 37–38 |
| Allgemeines RAM, 8 KiB | 0xFFE000–0xFFFFFF, aktiviert | S. 94–95, Tabellen 32–33 |
| EMAC-RAM, 8 KiB | 0xFFC000–0xFFDFFF, aktiviert | S. 94–95, Tabellen 32–33 |
| RAM_CTL, I/O 0x00B4 | 0xC0 | Tabelle 32 |
| RAM_ADDR_U, I/O 0x00B5 | 0xFF | Tabelle 33 |
| FLASH_ADDR_U, I/O 0x00F7 | 0x00, Bits 1:0 reserviert | Tabelle 37 |
| FLASH_CTRL, I/O 0x00F8 | 0x88: aktiviert, vier Wait States | Tabelle 38 |

RAM ist über RAM_ADDR_U verschiebbar: EMAC-RAM bei Offset 0xC000,
allgemeines RAM bei Offset 0xE000. Flash ist auf 256-KiB-Grenzen verschiebbar.
Dekodierungspriorität bei Überlappung: internes RAM vor internem Flash
vor externen Chip Selects (PS0192 S. 95, 104).
Die virtuelle Minimalplatine erhält zunächst keinen externen Speicher.
Konfigurationsflash und Programmier-/Löschverfahren bleiben separate Aufgaben.

## UART0 als erste Konsole

Dies sind I/O-Adressen, keine Speicheradressen. Quellen: PS0192 S. 35–36,
182–194, insbesondere Tabellen 102 und 106.

| I/O-Adresse | Register | Reset / Bedeutung |
| --- | --- | --- |
| 0x00C0 | RBR lesen / THR schreiben | Empfang / Senden bei DLAB=0 |
| 0x00C0 | BRG_L | 0x02 bei DLAB=1 |
| 0x00C1 | IER / BRG_H | 0x00; Auswahl durch DLAB |
| 0x00C2 | IIR lesen / FCTL schreiben | 0x01 / 0x00 |
| 0x00C3 | LCTL | 0x00; Bit 7 ist DLAB |
| 0x00C4 | MCTL | 0x00 |
| 0x00C5 | LSR | 0x60; THRE Bit 5, TEMT Bit 6 |
| 0x00C6 | MSR | Reset nicht festgelegt (XX) |
| 0x00C7 | SPR | 0x00 |

DLAB=1 schaltet C0/C1 auf die Baudratenteiler um. Ein Schreibzugriff auf
C0 darf dann kein Konsolenzeichen erzeugen. LCTL=0x03 wählt 8 Datenbits,
ein Stopbit und keine Parität. Die spätere Geräteimplementierung muss
FIFO-, Status- und Interruptverhalten ergänzen; permanente Sendebereitschaft
wäre nur ein ausdrücklich gekennzeichnetes vorläufiges Modell.
GPIO-Pinmultiplexing und Taktversorgung sind vor dem UART-Modell zu prüfen.

## Erster ausführbarer Meilenstein

1. QEMU-Version/Commit und Buildweg festhalten; CPU-/TCG-Anbindung prüfen.
2. F91-CPU-Zustand und minimale Z80-/ADL-Ausführung einbinden.
3. Resetabbild von Flash/RAM samt Remapping modellieren.
4. UART0 an QEMU-Zeichengerät anschließen.
5. Eigenes ROM ab Reset ausführen: ADL aktivieren, SPL im allgemeinen RAM
   setzen, UART initialisieren, LSR pollen und `Hello eZ80F91` ausgeben.

Abnahmekriterien: reproduzierbarer Build, erwartete Konsolenausgabe,
getesteter Z80-zu-ADL-Wechsel, korrekte DLAB-Umschaltung und klare
Diagnose bei nicht implementierten Befehlen/Geräten. Kleine unabhängige
CPU-Tests prüfen zusätzlich 16-/24-Bit-Grenzen und Stackzugriffe.
Ein erfolgreicher UART-Test belegt noch keine vollständige F91-Kompatibilität.
