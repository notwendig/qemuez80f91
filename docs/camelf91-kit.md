# CAMELF91: Taster und 5x7-LED-Matrix

Die Wörter sind im nativen ZDS-Projekt und im reproduzierbaren Polling-Build
enthalten. Das neu gebaute Debug-Image in ZDS laden und die CPU starten.
Für das emulierte Kit-Fenster den QEMU-Starter mit `./start.sh --kit`
aufrufen. Die Hardwarebelegung entspricht [kit.md](kit.md).

| Wort | Stackeffekt | Funktion |
| --- | --- | --- |
| `BUTTON-INIT` | `( -- )` | PB0..2 als GPIO-Eingänge einrichten. PB3..7 bleiben erhalten. |
| `BUTTONS` | `( -- mask )` | Gedrückte Taster: SW1=1, SW2=2, SW3=4, kombiniert 0..7. Richtet die Eingänge automatisch ein. |
| `BUTTON?` | `( n -- flag )` | Taster 1=links, 2=Mitte, 3=rechts; gedrückt liefert -1, sonst 0. Ungültige Nummern liefern 0. |
| `SW1?` `SW2?` `SW3?` | `( -- flag )` | Direkte Abfragen der drei Taster. |
| `MATRIX-INIT` | `( -- )` | Hintergrundscan starten. Wiederholte Aufrufe behalten das aktuelle Bild. |
| `MATRIX-CHAR` | `( char -- )` | ASCII-Zeichen anzeigen; startet die Anzeige automatisch. |
| `MATRIX!` | `( addr -- )` | Sieben aufeinanderfolgende Bytes als eigenes Bitmap übernehmen. |
| `MATRIX-CLEAR` | `( -- )` | Anzeige löschen; der Hintergrundscan bleibt aktiv. |
| `MATRIX-OFF` | `( -- )` | Anzeige löschen und Timer1 anhalten. |

```forth
BUTTONS .
1 BUTTON? .
SW2? .
CHAR A MATRIX-CHAR
CHAR 5 MATRIX-CHAR
MATRIX-CLEAR
MATRIX-OFF
```

`MATRIX-CHAR` unterstützt ASCII 32..126. Kleinbuchstaben verwenden die
Großbuchstaben-Glyphen. Alle anderen Zellwerte, auch negative Zahlen und
Werte über 255, ergeben ein Fragezeichen.

Eigene Bitmaps bestehen aus sieben Zeilen von oben nach unten. Pro Byte
steht Bit 4 für die linke und Bit 0 für die rechte LED; 1 bedeutet an.
Bits 5..7 werden beim Anzeigen ignoriert. Die sieben Bytes werden kopiert;
der Quellpuffer darf anschließend wiederverwendet werden.

```forth
CREATE DIAGONAL 16 C, 8 C, 4 C, 2 C, 1 C, 0 C, 31 C,
DIAGONAL MATRIX!
```

Die Anzeige verwendet Timer1 mit etwa 700 Zeilen pro Sekunde, entsprechend
100 vollständigen Bildern pro Sekunde. Der Interrupt erhält die Forth-
Register; die Konsole und Forth-Berechnungen laufen weiter. Zeilen werden
während des Spaltenwechsels dunkel geschaltet. Die Kit-Latches und Timer1
stehen während der Anzeige diesem Treiber zur Verfügung. Die bestehende
CS2-Abbildung des CAMEL-Boardstarts wird verwendet und nicht umprogrammiert.
Die Tasterabfrage liefert den momentanen Zustand ohne Software-Entprellung.

Eine einfache Demonstration steht in `examples/camelf91/kit-demo.fth`:

```forth
: BTN-DEMO BEGIN BUTTONS 48 + MATRIX-CHAR KEY? UNTIL KEY DROP MATRIX-OFF ;
BTN-DEMO
```

Die Anzeige zeigt die Drückmaske 0..7, eine beliebige Taste in der UART-
Konsole beendet die Schleife und schaltet die Matrix aus.

## Quellen und Tests

`examples/camelf91/kit.inc` ist die gemeinsame Treiberquelle;
`kit_font.py` erzeugt den expliziten Zeichensatz `kit_font.inc`.
Die identischen Includes liegen für den nativen ZDS-Build unter
`subprojects/CAMELF91_24/asm/`. Der Polling-Builder prüft deren Übereinstimmung.

```sh
make -C subprojects/CAMELF91_24
python3 tests/test_camelf91_kit.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
python3 tests/test_camelf91_words.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
```

Der Kit-Test prüft alle acht Drückmasken, Loslassen, ungültige Tasternummern,
Erhalt von PB3..7, ASCII-/Ersatzzeichen, Bitmuster und Pixelorientierung,
laufenden Multiplexbetrieb während Berechnungen, Löschen/Abschalten und
erneutes Starten nach Hardware-Reset. Er vergleicht sowohl den Gastpuffer
als auch die integrierte Anzeige des Boardmodells mit den erwarteten Pixeln.
