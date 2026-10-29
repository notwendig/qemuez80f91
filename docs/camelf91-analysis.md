# CAMELF91: Analyse und Kernkorrekturen

Geprüft wurde der festgelegte Upstream-Commit
`b975f3acac08c70c05d951aad22e5c1824446206`, mit demselben ZDS-5.3.5-Build,
Polling-Adapter und QEMU wie beim ersten Integrationstest. Die folgenden
Fehler sind im Forth-Kern reproduziert. Für diese Korrekturen waren keine
weiteren Änderungen am Emulator nötig.

## Befunde

| Bereich | Reproduktion | Vorher | Korrigiert |
| --- | --- | --- | --- |
| Stacktiefe | `DEPTH .` auf leerem Stack | `-267804` | `0` |
| Stacktiefe | `1 2 3 DEPTH .` | `-267799` | `3` |
| Exakte negative Division | `-6 3 /MOD . .` | `-3 3` | `-2 0` |
| Negativer Quotient nahe null | `1 -3 /MOD . .` | `0 1` | `-1 -2` |
| Vorzeichen in 48-Bit-Summe | `0 1 -1 M+ . .` | `1 -1` | `0 -1` |
| Voller Eingabepuffer | vier Zeichen bei `ACCEPT` mit Kapazität 4 | Länge 3 trotz vier gespeicherter Zeichen | Länge 4 |
| Eingabe ohne Kapazität | `ACCEPT` mit Kapazität 0, Eingabe XYZ | Länge -1 und Speicher verändert | Länge 0, Speicher unverändert |

Bei `/MOD . .` wird zuerst der Quotient, dann der Rest ausgegeben.
Bei `M+ . .` wird zuerst die obere, dann die untere 24-Bit-Zelle ausgegeben.
Die konkreten ursprünglichen DEPTH-Fehlwerte gelten für das bisherige Testimage.

### DEPTH: falsche Zellbreite und indirekter Stackanfang

`S0` ist im 24-Bit-Port eine User-Variable. Der alte Code verwendete ihre
Adresse statt ihres Inhalts und teilte den Abstand durch zwei statt durch
drei. Korrigiert ist die Berechnung `SP@ S0 @ SWAP - 3 /`.
Sie zählt die bereits vorhandenen Stackzellen, auch in kompilierten Wörtern.
Das entspricht der Definition von
[DEPTH im Forth-Standard](https://forth-standard.org/standard/core/DEPTH).

### FM/MOD: Rundung anhand des Rests

Der alte Code korrigierte jedes negative symmetrische Quotientenergebnis.
Das ist bei exakter Teilung falsch und übersieht Quotienten null, die bei
unterschiedlichen Vorzeichen abgerundet werden müssen. Jetzt wird nur
korrigiert, wenn der Rest ungleich null ist und sein Vorzeichen vom Divisor
abweicht. Dadurch liefern auch `/`, `MOD`, `*/` und `*/MOD` über ihre bestehende
Definition die korrigierte Rundung. Als Referenz dient
[FM/MOD](https://forth-standard.org/standard/core/FMDivMOD); die bisherigen
Wörter verwenden ausdrücklich dessen nach unten gerundete Division.
Division durch null und nicht darstellbare Quotienten sind nicht Teil dieser
Regression, weil der Standard sie als mehrdeutig definiert.

### M+: negative Einzelzelle auf Doppelzelle erweitern

Der alte ASM-Code addierte die untere Zelle und übernahm nur deren Übertrag
in die obere Zelle. Ein negatives 24-Bit-Argument benötigt zusätzlich eine
Vorzeichenerweiterung: zur oberen Zelle wird FFFFFF addiert, also eins
subtrahiert. Das Addendenvorzeichen wird vor der Addition gesichert; danach
werden Übertrag und Vorzeichenerweiterung getrennt berücksichtigt.
Die Summe wird modulo 48 Bit gespeichert. Grundlage ist die signierte
Einzelzelle in [M+](https://forth-standard.org/standard/double/MPlus).

### ACCEPT: exklusive Endadresse und begrenzte Schreibzugriffe

Die bisherige Schleife rechnete mit `start+n-1`, schrieb aber vor der
Grenzprüfung. Dadurch stimmten gespeicherte Länge und Rückgabewert bei vollem
Puffer nicht überein. Jetzt wird mit der exklusiven Endadresse `start+n`
gearbeitet und nur geschrieben, solange der aktuelle Zeiger darunter liegt.
Backspace bleibt an der Startadresse stehen; auch Startadresse null führt
nicht mehr zum Zeigerunterlauf. Bestehendes Echo und CR als Terminator bleiben
erhalten. Überzählige Zeichen werden bis CR konsumiert und nicht gespeichert.

[ACCEPT](https://forth-standard.org/standard/core/ACCEPT) verlangt den
Rückgabewert als Länge der tatsächlich gespeicherten Zeichen. Länge null ist
laut Standard ein mehrdeutiger Fall. Das Projekt definiert dafür zusätzlich
ein defensives Verhalten: Zeichen bis CR konsumieren, nichts schreiben,
null zurückgeben. Diese Zusatzregel wird nicht als Standardanforderung
bezeichnet. Guard-Bytes prüfen unveränderten Speicher vor und hinter dem
Puffer; getestet sind Kapazitäten 0, 1 und 4, Überlänge und Backspace.

## Umsetzung und Reproduzierbarkeit

Die Änderungen stehen im überschaubaren Patch
`patches/camelf91/0001-fix-24bit-core.patch`. Er ändert ausschließlich
`CAMLF91e.asm` und `CAMLF91h.asm`. Startup, Dictionary-Modell und Konsolen-ABI
bleiben erhalten. Das Git-Submodul bleibt auf dem unveränderten Upstream-Commit.
Der Builder kopiert die Quellen, wendet den Patch isoliert an und übersetzt
die korrigierte Kopie. Er speichert den Patchhash und die Hashes der tatsächlich
verwendeten Quellen in `camel.json`.

Zusätzlich verweigert der Builder Ausgabeverzeichnisse innerhalb des
Quellcheckouts und nimmt nur die bekannten Eingabedateien in sein Manifest
auf. Alte zusätzliche ASM-Dateien in einem wiederverwendeten Buildverzeichnis
werden dadurch nicht fälschlich als Quellen des neuen Builds ausgewiesen.

Das neue `camel.bin` hat 9350 Bytes; die Map weist 9353 belegte ROM-Bytes aus.
Der unveränderte RAM-Bedarf liegt bei 432 Bytes plus den reservierten
Forth-Stacks/Arbeitsbereichen. Die drei zusätzlichen reservierten ROM-Bytes
werden wie bisher nicht ins Raw-Image ausgegeben.

## Regression

`examples/camelf91/commands.json` enthält 83 konkrete Fälle. Der UART-Test
führt sämtliche Fälle vor und nach Systemreset aus und prüft die Antworten
zeichengetreu, anschließend auch Dictionary-Neustart, User-Zeiger und HALT.

Zusätzlich zu den bisherigen Integrationsfällen enthalten sind:

- DEPTH bei leerem und belegtem Stack sowie in einem kompilierten Wort.
- Negative Divisionen aller Vorzeichenkombinationen, exakte Ergebnisse,
  Quotienten null und die Grenzen des signierten 24-Bit-Bereichs.
- M+ mit negativen Argumenten, Übertrag und Vorzeichenwechseln.
- ACCEPT mit Guard-Bytes, exakter Kapazität, Überlänge und Backspace,
  einschließlich Startadresse null ohne Speicheränderung.
- UM* und gültige UM/MOD-Fälle über den vollen 24-/48-Bit-Bereich.

Die zusätzlichen Arithmetikvektoren wurden mit unabhängiger Python-
Ganzzahlarithmetik berechnet; die deterministische Auswahl verwendet Seed
`0xCAFE91`. Der Test nutzt die fest gespeicherten Ein-/Ausgabewerte.
Das ist eine gezielte Kernregression und kein vollständiger Nachweis aller
ANS-Forth-Wörter. Der bisherige Polling-BSP und das Debug-RAM-Profil bleiben
der getestete Einbindungspfad.

## Abschlussprüfung

Alle zwölf Integrationstestskripte bestanden. Die 83 Forth-Fälle wurden
vollständig vor und nach Reset ausgeführt. Ein unabhängiger Neubau erzeugt
dasselbe Image und dieselben Metadaten. Der gespeicherte Patch lässt sich
auf die ursprünglichen Quellen anwenden; die resultierenden Quellhashes
stimmen mit den tatsächlich übersetzten Dateien überein. Das Submodul
bleibt unverändert auf dem festgelegten Commit.
