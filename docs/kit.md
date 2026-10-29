# eZ80F91 Development Kit: LED-Matrix und Taster

```sh
./start.sh --kit
./start.sh --run --kit
./start.sh --kit dbgport 4041
```

`--kit` öffnet zusätzlich zur UART-Konsole ein Kit-Fenster. Ohne `--run`
wartet die CPU weiterhin auf ZDS. Das Schließen des Kit-Fensters beendet
nur die Anzeige; das Beenden der UART-Konsole beendet auch das Kit-Fenster.
Python mit Tkinter ist erforderlich.

CAMELF91 bietet dafür [Forth-Wörter für Taster und Matrix](camelf91-kit.md),
zum Beispiel `BUTTONS .` und `CHAR A MATRIX-CHAR`.

Die Abbildung folgt UM014220-0508, Tabellen 8, 9 und 15 sowie der
Zilog-QuickStart-LED-Demo-Ausrichtung: sieben Zeilen, fünf Spalten.

| Adresse | Funktion |
| --- | --- |
| 800000h | Anodenbits 0–6 aktiv High; Bit 7 schaltet GPIO auf Eingang |
| 800001h | Kathodenbits 0–4 aktiv Low; Bits 5/6/7: Modem-Reset/Trig1/Trig2 |
| 800002h | GPIO-Latch; Eingänge liefern mangels externer Beschaltung FFh |

Im Fenster steht Anodenbit 0 für die oberste LED-Zeile, Bit 6 für die
unterste. Kathodenbit 4 steht links und Bit 0 rechts. Anoden- und
Kathodenregister sind nur beschreibbar und liefern beim Lesen FFh;
der GPIO-Datenlatch ist les-/schreibbar. Die Resetdarstellung ist dunkel.

Die Platinenregister sind nur mit `--kit` eingeblendet. CS2 muss ein gültiges
aktiviertes Speicherfenster über 800000h besitzen. Höher priorisierte CS0/CS1
und interner Speicher behalten Vorrang. Ohne `--kit` bleiben diese Adressen
Bestandteil der bisherigen Speicherabbildung.

QEMU integriert die Leuchtdauer je LED über einen vollständigen Scan aller
sieben Zeilen und filtert sehr kurze Umschaltimpulse. Erst wenn auch die
letzte Zeile ihre Leuchtzeit beendet hat, wird das neue Bild veröffentlicht.
Bis dahin hält das Kit-Fenster das vorige vollständige Bild, auch bei einem
langsamen oder im Debugger angehaltenen Scan. Das Fenster zeichnet die LEDs
nur bei einer geänderten vollständigen Pixelmaske neu; Register und Taster
werden unabhängig davon weiter aktualisiert. Jeder vollständige Scan wird
übernommen, auch wenn sich die Laufschrift in jedem Durchlauf verändert.
Identische Wiederholungen sind nicht erforderlich: Eine solche Bedingung
kann fortlaufend wechselnde Bilder blockieren. Statisch dunkle oder parallel
angesteuerte Anzeigen werden nach 40 ms unverändertem Anodenregister
übernommen. Statische Debuggerproben vor dem ersten CPU-Start bleiben direkt
sichtbar. Die Anzeige ist eine funktionale Darstellung, keine Simulation
von LED-Strom, elektrischer Helligkeit oder des GAL-Timings. Die vier optionalen
Modem-Status-LEDs D1–D4 werden mangels Modemmodell nicht simuliert; die im
Fenster angezeigten Modem-/Triggerwerte sind ausschließlich die Latchbits.

Der Zustand wird unter `/tmp/ez80f91-<uid>/<port>.kit.json` bereitgestellt.
Direkter QEMU-Aufruf: `-global ez80f91-memory.kit-led-state=/tmp/kit.json`.
Der Starter verwaltet Anzeige und Zustandsdatei gemeinsam mit der Instanz.

```sh
python3 tests/test_kit.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
python3 tests/test_kit_frames.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
```

Der Test prüft Polarität/Ausrichtung, GPIO-Richtung, CS-Freigabe/Priorität,
Reset und ein echtes Gastprogramm mit siebenfacher Multiplexdarstellung.
Der Frame-Test hält den Gast nach jeder einzelnen Zeile an. Er prüft,
dass selbst bei mehr als 40 ms Gastzeit pro Zeile keine Teilbilder erscheinen
und neue Zeichen sowie ein vollständig dunkles Bild erst nach Zeile sieben
sichtbar werden. Der Forth-Treiber wird hierfür nicht verändert.
Die Regression verwendet außerdem Live-Pixelmasken der FreeRTOS-Laufschrift
und wechselt das Bild in jedem Scan. Der Test reproduzierte den Stillstand
mit der früheren Bestätigung durch zwei identische Bilder und prüft nun,
dass jede vollständige neue Position erscheint, einschließlich eines
anschließend vollständig dunklen Bildes.

## Kit-Taster

SW1 (links), SW2 (Mitte) und SW3 (rechts) sind mit PB0, PB1 und PB2
verbunden. Mit der Maus gedrückt halten oder die Tastaturtasten 1–3 verwenden.
Loslassen, Fokusverlust und Schließen des Fensters geben gedrückte Taster frei.
Die Eingänge sind aktiv Low. SW4 Reset löst einen Systemreset der Emulation aus.

Das Fenster verwendet den lokalen QMP-Socket neben der Zustandsdatei
(`<port>.qmp`); mit `--qmp` kann ein anderer Socket angegeben werden.
Die Laufzeiteigenschaft `kit-buttons` des Speichergeräts enthält die
Drückmaske 0–7. PB_DR/PB_DDR/PB_ALT1/PB_ALT2 liegen an 9A–9Dh;
Dual-Edge-Interrupts gehen an A0h/A4h/A8h. Schreiben von Einsen nach PB_ALT0
(A7h) quittiert sie. Andere GPIO-Interruptmodi werden noch nicht modelliert.

```sh
python3 tests/test_kit_buttons.py /tmp/qemuez80f91-build-baseline/qemu-system-ez80
```

Dieser Test verwendet den QMP-Bedienweg des Fensters und prüft Eingänge,
Drück-/Loslassinterrupts, Quittierung und Reset mit echten Gast-ISRs.
