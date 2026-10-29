# CAMELF91_24 als festes Sub- und Testprojekt

## Einbindung und Quellstand

`subprojects/CAMELF91_24` ist ein Git-Submodul von
https://github.com/notwendig/CAMELF91_24, festgelegt auf Commit
`b975f3acac08c70c05d951aad22e5c1824446206`.
Der Build prüft diesen Commit und unveränderte Upstream-ASM-/Debugquellen.
Anschließend wendet er die [analysierten Kernkorrekturen](camelf91-analysis.md)
als separaten Patch auf eine Buildkopie an.
Der Forth-Kern meldet Version 1.1.0, 24 Bit, Debug.

```sh
sh scripts/setup-camelf91.sh
python3 examples/camelf91/build.py --zds /pfad/zu/ZDSII_eZ80Acclaim!_5.3.5
```

Der Setup ruft Submodule absichtlich nicht rekursiv ab. Das Originalprojekt
verweist bei `libbsp` auf eine lokale SSH-Hostkonfiguration und den Commit
`f459c87dcf631ffe594f517892fe0497aa1a0a3b`, der beim angegebenen öffentlichen
BSP-Upstream nicht mehr abrufbar ist. Ein aktueller, anderer BSP-Commit wird
für diesen Test nicht stillschweigend an dessen Stelle eingesetzt.

Stattdessen enthält `examples/camelf91/poll_bsp.asm` einen getrennten
Polling-Adapter für `init_bsp`, `putc`, `getc` und `kbhit`; `console.inc`
deklariert die verwendete Konsolen-ABI. Er initialisiert UART0 für 115200,
8N1 bei 50 MHz und verwendet weder FIFO noch UART-Interrupts. Das passt zum
bisherigen UART-Modell. Dieser Adapter ersetzt das BSP für den Emulatortest;
er ist kein Nachweis für das originale BSP, dessen Interrupttreiber oder EMAC.

Die vier Kernelmodule und ihre Includes stammen aus dem festgelegten Commit;
`CAMLF91e.asm` und `CAMLF91h.asm` erhalten vor der Übersetzung den
Korrekturpatch für DEPTH, FM/MOD, M+ und ACCEPT. `vectors24.asm`,
`init_params_f91.asm`, `cstartup.asm` und `zsldevinitdummy.asm` bleiben
unverändert. Dictionary-Modell und Konsolen-ABI werden beibehalten.
Die originalen Lizenzhinweise bleiben im Submodul erhalten. Das Repository
enthält sowohl eine GPLv3-Datei als auch gesonderte Hinweise in README und
Quellköpfen; die Einbindung ändert diese Hinweise nicht.

## Build und Speicherprofil

Der gespeicherte Builder verwendet ZDS 5.3.5 unter Wine statt der im Original
fest eingetragenen lokalen ZDS-5.3.4-Pfade. Buildprodukte landen außerhalb des
Submoduls in `build/camelf91` oder dem mit `--out` gewählten Verzeichnis.
Die Speicher-/Taktdefinitionen stammen aus der Original-Debug-Linkerdatei:

| Bereich | Belegung |
| --- | --- |
| ROM/Modul-SRAM | 000000–07FFFF |
| RAM-Linkerbereich | B7D000–BFFFFF |
| Interner SRAM/EMAC-RAM | auf Seite B7 umgelegt |
| Externes hohes SRAM | B80000–BFFFFF |
| Oberes Stackende | C00000, erstes Push darunter |
| Takt | 50-MHz-Oszillator, PLL aus |

Für den Test werden Ausgabepfade und Objektliste der Linkerdatei angepasst,
das Test-BSP statt `libbsp` eingebunden und `__cstartup=1` explizit gesetzt.
So werden BSS und DATA durch den Original-C-Startup initialisiert.
Der QEMU-Start verwendet das vorhandene `ez80f91-freertos,ram-boot=on`-Profil;
die Originalinitialisierung setzt danach die CAMEL-eigene Speicherbelegung.

`examples/camelf91/camel.bin` ist 9350 Bytes groß. Die Linker-Map meldet
9353 belegte ROM-Bytes einschließlich nicht ausgegebener Reservierungen.
`camel.map` und `camel.json` sichern Symboladressen, Commit und SHA-256 der
Quellen, des Korrekturpatches bzw. des Images. Die Originalquellen bleiben im Submodul.

## Interaktiver Start

```sh
build/ez80/qemu-system-ez80 -M ez80f91-freertos,ram-boot=on -kernel examples/camelf91/camel.bin -icount shift=0 -display none -monitor none -serial mon:stdio
```

Nach dem Banner beispielsweise eingeben:

```forth
1 2 + .
: SQUARE DUP * ;
123 SQUARE .
```

Erwartet werden `3`, `OK` und anschließend `15129`, `OK`.
`bye` hält die Gast-CPU an; Ctrl-A X beendet QEMU.

## Automatischer Test

```sh
python3 tests/test_camelf91.py build/ez80/qemu-system-ez80
python3 tests/test_camelf91.py build/ez80/qemu-system-ez80 build/camelf91/camel.bin
```

Der Test benötigt einen lokalen Unix-Socket für den UART-Ein-/Ausgabestrom.
Er prüft das genaue Banner und sämtliche Antworten auf die 83 Testfälle in
`examples/camelf91/commands.json`:

- Addition und 24-Bit-Überlauf von FFFFFF nach null.
- Division mit Rest und Multiplikation.
- Kompilieren und Ausführen eigener Wörter.
- DO/LOOP und IF/ELSE/THEN.
- 24-Bit-Variablen, Bytezugriffe und überlappenden rückwärtigen Speichertransfer.
- Logische Schiebeoperationen und Rücksprungstack.

Nach `bye` prüft der Test den Halt-PC, ADL und den User-Zeiger. Der
Dictionary-Pointer muss durch das Kompilieren gewachsen sein. Anschließend
folgen Systemreset, erneuter Banner, Dictionary-Pointer auf Originalwert und
alle Eingaben ein zweites Mal. Es ist ein konkreter Integrationstest und
keine vollständige ANS-Forth-Konformitätsprüfung. Details der gefundenen
Fehler und ihrer Grenzfalltests: [Analyse](camelf91-analysis.md). Release-/Chiponly-Flashbuild,
Original-BSP und Netzwerkfunktion sind nicht Teil dieses Testpfads.

## Ergänzte CPU-Funktionen

- CPI/CPIR/CPD/CPDR mit Zähler, Adressrichtung und dokumentierten Flags.
- LDD/LDDR für rückwärtige Speichertransfers.
- Byte-ALU über `(IX+d)` und `(IY+d)`.
- CB-Rotationen/Schieben sowie indizierte BIT/RES/SET; der undokumentierte
  SLL-Opcode bleibt ungültig und löst den Hardware-TRAP aus.
- CPL, DJNZ und bedingte CALLs.

Grundlage sind die Befehlsbeschreibungen in UM007715-0415, insbesondere
Blockvergleich, Blocktransfer, bedingter CALL, DJNZ und CB-Befehle.
`tests/test_cstartup_ops.py` prüft gezielt Flags, Vorzeichenoffsets,
überlappende Transfers, Stackbreite und alle acht CALL-Bedingungen.

## Validierung

Alle zwölf Integrationstestskripte bestanden. Ein unabhängiger Neubau
reproduziert `camel.bin` und `camel.json` exakt. Das Submodul ist unverändert
und der Setup prüft seinen festgelegten Commit; der Builder patcht nur die
Buildkopie. Die QEMU-Änderungen sind im
aktualisierten Gesamtpatch gesichert; die Anwendung auf unveränderte
Basisdateien wurde geprüft.
