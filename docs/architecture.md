# Entwurf

## CPU und Maschine

CPU und SoC/Platine werden getrennt modelliert. Der CPU-Kern behandelt den
eZ80-Befehlssatz, die Register und die Ausführungsmodi. Das F91-Modell enthält
die integrierten Geräte und deren Speicher-/I/O-Dekodierung. Ein separates
Platinenmodell legt externe Bausteine, Takt und Speicher fest.

Ein gewöhnlicher Z80-Kern genügt nicht als eZ80-Kern. Insbesondere müssen
ADL, 24-Bit-Arithmetik, Befehlslängen, Moduspräfixe, Rücksprungadressen,
Stackauswahl und Interrupt-Rückkehr zusammenhängend implementiert werden.

## Erste ausführbare Ausbaustufe

Die erste Ausbaustufe soll ein kleines, dokumentiertes Test-ROM ausführen
und dessen UART-Ausgabe liefern. Nicht implementierte Geräte sollen als
solche erkennbar bleiben. Erfolgreiche ROM-Ausführung ist kein Nachweis
vollständiger F91-Kompatibilität.

Die Speicher- und Registeradressen werden vor der Implementierung aus dem
eZ80F91-Datenblatt übernommen und in einer eigenen Speicherübersicht dokumentiert.
Das im anderen Projekt entworfene `mmuport`-Banking gilt hier nicht automatisch.

## QEMU-Anbindung

Vor der Festlegung auf eine Implementierung werden folgende Punkte geprüft:

- Verwendbare offizielle QEMU-Basis und Reproduzierbarkeit des Builds.
- TCG-Integration gegenüber einem eingebetteten Interpreter und deren
  Auswirkungen auf Debugging, Zeitmodell und Wartung.
- Verfügbarkeit und Lizenz eines bestehenden eZ80-Kerns.
- Abgrenzung von CPU-Eigenschaften und F91-spezifischen Peripheriefunktionen.

Gewählt ist die reguläre TCG-Anbindung auf QEMU 11.1.2.
Version, Integrationspunkte und Basisbuild: [QEMU-Basis](qemu-base.md).
Es ist noch kein fremder eZ80-Kern übernommen.

## Zeitmodell und Genauigkeit

Funktionale Ausführung, Befehlslaufzeiten und elektrische Bus-Signalverläufe
sind getrennte Anforderungen. QEMU-TCG allein garantiert keine Busgenauigkeit.
Falls eine Takt- oder Flankenschnittstelle benötigt wird, muss sie ausdrücklich
entworfen und gegen das eZ80F91-Verhalten geprüft werden. NMOS-Z80-Laufzeiten
werden nicht auf den eZ80 übertragen.

## Prüfschwerpunkte

- 16-/24-Bit-Adressgrenzen und Moduswechsel.
- Registerbreiten, Präfixe, zusätzliche eZ80-Befehle und Flags.
- Calls, Returns und Interrupts über Modusgrenzen hinweg.
- Resetbelegung, Speicherdekodierung und Schreibschutz.
- UART und danach Interrupt-/Timerverhalten mit eigener Firmware.

Prüfergebnisse müssen die getestete CPU-/SoC-Ausbaustufe nennen. Eine
pauschale Zusage von 100 Prozent Kompatibilität erfolgt erst bei entsprechendem
Nachweis.
