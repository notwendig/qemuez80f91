# Dynamische externe Speicherfenster CS0–CS3

Alle vier Chip-Selects bilden ihren externen Speicher anhand der F91-Register
CSx_LBR, CSx_UBR und CSx_CTL ab. Feste Ausschnitte bei 000000h und B80000h sind
nicht mehr Voraussetzung. Dies gilt für beide Maschinenprofile.

## Auswahl RAM/Flash

Die CS-Register wählen Adressen, Speicher-/I/O-Zugriff und Freigabe. Der Typ des
angeschlossenen Bausteins ist eine Board-Einstellung beim Start:

| Option | Standard | Baustein |
| --- | --- | --- |
| `cs0` | `flash` | AMD-NOR mit 1 MiB und Bottom-Boot-Geometrie |
| `cs1` | `ram` | RAM |
| `cs2` | `ram` | RAM |
| `cs3` | `ram` | RAM |

Jede Option akzeptiert `ram`, `flash` oder `none`. Beispiel:

```sh
qemu-system-ez80 -M ez80f91-freertos,ram-boot=on,cs0=flash,cs1=ram,cs2=ram,cs3=flash -kernel image.bin
```

Die Starter reichen diese Einstellungen ebenfalls weiter:

```sh
python3 -m tools.demo --cs3 flash
python3 tools/zds/f24.py --cs3 flash
```

Die Diagnoseprobe unterstützt dieselben `--cs0`–`--cs3`-Optionen. Die
Bausteinauswahl ist während des VM-Laufs fest; die Fenster werden weiterhin
vom Gast beliebig über die CS-Register umprogrammiert.

`none` bezeichnet einen unbestückten Anschluss. Ein aktivierter, höher
priorisierter CS unterdrückt auch dann die niedrigeren CS. Lesen liefert in
diesem Fall den unzugewiesenen Buswert 00h; Schreiben wird ignoriert.

## Registerwirkung

Ein Speicherfenster ist sichtbar, wenn CSx_CTL Bit 3 (EN) gesetzt, Bit 4 (IO)
gelöscht und UBR mindestens so groß wie LBR ist:

```
Start = LBR << 16
Ende  = ((UBR + 1) << 16) - 1
Größe = (UBR - LBR + 1) * 64 KiB
```

LBR=UBR aktiviert eine einzelne 64-KiB-Seite. Für CS3 beispielsweise:

```
OUT0 (B3h), 00h    ; Fenster abschalten
OUT0 (B1h), 60h    ; LBR
OUT0 (B2h), 63h    ; UBR
OUT0 (B3h), 08h    ; Speicherfenster 600000h–63FFFFh einschalten
```

Jeder Registerschreibzugriff aktualisiert die Abbildung sofort. Beim
Umprogrammieren des Bereichs sollte die Firmware den CS zunächst abschalten,
wenn eine vorübergehende Überlappung sonst laufenden Code überdecken würde.
Das Setzen des IO-Bits entfernt das Speicherfenster. Externe I/O-Bausteine
werden in dieser Erweiterung noch nicht angeschlossen.

Interner RAM einschließlich EMAC-RAM hat Vorrang vor internem Flash; danach
folgen CS0, CS1, CS2 und CS3. Deaktivieren eines Fensters legt den darunter
liegenden Speicher wieder frei. Ungültige Grenzen deaktivieren den CS.

## Speicherinhalt und Flash-Protokoll

Jede RAM-Bank besitzt einen stabilen, virtuell reservierten 16-MiB-Speicher.
Das jeweils sichtbare Fenster beginnt bei Bankoffset 0. Verschieben zeigt
also dieselben Bytes an der neuen Basis; Verkleinern verwirft den ausgeblendeten
Inhalt nicht. Nicht benutzte RAM-Seiten werden über den Host bedarfsweise
belegt. Die anfänglichen RAM-Inhalte sind 00h.

Für `flash` wird QEMUs bestehendes `pflash_cfi02` verwendet: 8-Bit-AMD-NOR,
IDs 01h/37h, 1 MiB mit Bootsektoren 16 KiB, 2×8 KiB, 32 KiB und 15×64 KiB.
Die Modellgeometrie entspricht dem AM29LV008BB; der generische QEMU-Baustein
stellt zusätzlich seine CFI-Abfrage bereit. Fenster über 1 MiB spiegeln den
Chipinhalt im 1-MiB-Abstand. Ein kleineres Fenster macht entsprechend weniger
Chipinhalt zugänglich.

Geprüft sind AMD-Unlock bei 555h/2AAh, ID-Lesen, Byteprogrammierung mit NOR-
Verhalten, Sektorlöschen und CFI-QRY. Ein normaler RAM-Schreibzugriff ersetzt
bei Flash kein Program-Kommando. Frischer Flash enthält FFh. RAM- und Flash-
Inhalte bleiben über Abschalten, Remapping und Systemreset bestehen. Eine
Persistenzdatei über QEMU-Prozessneustarts ist noch nicht angeschlossen.

Interner Haupt-Flash und seine separate Informationsseite bleiben eigene
Bausteine. Die bisherigen Grenzen der internen Flash-Programmierung werden
hierdurch nicht verändert. Waitstates und externe Bustaktsignale werden nicht
zyklusgenau simuliert. Die Bankoffset-Abbildung ist das generische Boardmodell;
eine abweichende physische Verdrahtung der Adressleitungen wird nicht abgeleitet.

## Startprofile und Prüfung

Der normale Silizium-Reset behält CS0=00h–FFh/CTL=E8h und deaktivierte
CS1–CS3. Im ausdrücklich gewählten RAM-Debugprofil startet CS0 dagegen
abgeschaltet, CS1 deckt 000000h–07FFFFh ab und CS2 800000h–BFFFFFh. So kann das
originale ZDS-Startup CS0 umprogrammieren, ohne kurzzeitig den laufenden
SRAM-Code durch leeren Flash zu überlagern. Anschließend gelten ausschließlich
die vom Gast gesetzten Grenzen/Freigaben.

```sh
python3 tests/test_chip_selects.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
```

13 Ausführungsproben prüfen RAM und AMD-Flash an jedem CS, Bereichswechsel,
Verkleinern/Vergrößern, Abschalten, IO-Auswahl, ungültige Grenzen, Prioritäten
inklusive unbestücktem CS, CFI und Inhalts-Erhalt über Systemreset.
Die bisherigen 17 lokalen Testprogramme einschließlich dieser neuen Proben
bestehen; zusätzlich die echte Nexus-/ZDS-II-DLL-Anbindung. Das ZTP-Demo mit
RAM-Dateisystem besteht weiterhin DHCP von nadibox, 1000 Byte UDP und 4000
Byte TCP über das reale Netz.

Der vorhandene ZTP-Linkerrahmen setzt CS0_CTL weiterhin auf 0. Der vollständige
ZFS-Test auf externem Flash benötigt eine passende CS0-Freigabe und ist noch
nicht als Referenztest übernommen. Der normale Demo-Starter verwendet weiter
das geprüfte RAM-Dateisystem.
