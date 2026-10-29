# CAMELF91: Test aller Wörterbuch-Einträge

Der native Debug-Build enthält 237 Wörter. Der vollständige Testlauf am
29.10.2026 bestand mit 201 Stack-/Ergebnisprüfungen und ohne Fehler.
Alle 237 ROM-Wörter wurden tatsächlich ausgeführt. Das wird anhand ihrer
Einsprungadressen im QEMU-Ausführungstrace gemessen, einschließlich indirekter
Aufrufe durch Compiler und Interpreter. Es ist kein Nachweis aller möglichen
Eingaben oder Ausführungspfade eines Wortes.

## Ausführen

```sh
make -C subprojects/CAMELF91_24
python3 tests/test_camelf91_words.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
```

Der Runner startet ein eigenes QEMU mit dem nativen `Debug/camel_f91.hex` und
der passenden Mapdatei. Eine laufende ZDS-Sitzung auf Port 4040 wird dabei nicht
benutzt. `--hex`, `--map` und `--out` wählen andere Buildprodukte bzw. das
Berichtsverzeichnis.

Unter `build/camelf91-words/` entstehen:

- `report.md`: Ergebnis und Trefferzahl für jedes einzelne Wort.
- `report.json`: dasselbe maschinenlesbar, einschließlich Image-SHA256,
  Wortadressen, Fehlern und nicht ausgeführten Wörtern.
- `uart.log`: vollständiges Konsolenprotokoll.
- `entry-trace.log`: ein Ausführungsbeleg pro erreichtem Einsprungpunkt.

Der Prozess liefert einen Fehlerstatus, sobald ein Ergebnis falsch ist,
die UART hängen bleibt oder mindestens ein Wörterbuch-Eintrag nicht erreicht
wird. Das Wörterbuch wird aus der Linkkette des tatsächlich getesteten Images
gelesen; eine neue Definition kann somit nicht unbemerkt aus der Abdeckung fallen.

## Forth-Datei für die Konsole

`examples/camelf91/all-words.fth` enthält den selbstprüfenden Teil als Forth-
Quelltext. Zeilen einzeln übertragen und jeweils auf `OK` warten. Jede Zeile
passt in den 124 Zeichen langen Eingabepuffer. Ein bloßes Einfügen der ganzen
Datei kann den UART-Empfangspuffer überlaufen.

Die Datei endet mit `TEST-REPORT`. Erwartet wird:

```text
TESTS 198 FAILURES 0
```

`examples/camelf91/word_tests.py` ist die gemeinsame Quelle für diese Datei
und die automatisierten Fälle. `python3 examples/camelf91/word_tests.py`
erzeugt die Forth-Datei erneut.

Der vollständige Python-Lauf ergänzt drei interaktive Prüfungen für `KEY`,
`KEY?` und `ACCEPT`, kontrolliert `WORDS`, `MEMCFG` und `DUMP`, prüft
`QUIT`, `ABORT` und `ABORT"` sowie den Dictionary-Neustart durch `COLD`.
Am Ende wird `bye` ausgeführt und die HALT-Adresse kontrolliert.
`RESET` wird als interner Bestandteil von `COLD` erreicht; ein isolierter
Aufruf ist kein allgemeiner Neustart der Interpreter-Sitzung.

Die Portwörter verwenden ausschließlich das UART0-Scratchregister C7h und
stellen seinen alten Wert wieder her. Compilerhilfen werden durch reguläre
Definitionen und gezielt erzeugte Codefelder geprüft.

## Gefundener Fehler und zusätzliche Regression

`.R` und `D.R` gaben negative Zahlen ohne Minuszeichen aus. In `D.R` fehlte
das `ROT` vor `SIGN`: Nach `#S` liegt das aufbewahrte Vorzeichen unter der
Doppelzelle und muss zuerst nach oben gebracht werden. Die gemeinsame
Implementierung ist im nativen Quelltext und im Core-Patch korrigiert.

Die bestehende Regression `tests/test_camelf91.py` enthält jetzt 89 Fälle,
darunter sechs zusätzliche Formatierungsfälle mit negativen, positiven und
48-Bit-Grenzwerten. Alle 89 Fälle bestanden vor und nach Systemreset.
