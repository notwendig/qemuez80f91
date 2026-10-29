# CamelForth für eZ80F91

`subprojects/CAMELF91_24` ist ein eigenständiges Git-Submodul mit einem
24-Bit-CamelForth, Original-ZDS-Boardstart und Development-Kit-Wörtern.
Der historische geprüfte Kern basiert auf Commit
`b975f3acac08c70c05d951aad22e5c1824446206`; der aktuelle Projektstand wird
über den Gitlink des Workspace festgelegt und enthält die nativen Korrekturen.

## Zwei Buildwege

| Weg | Konsole und Ausgabe | Zweck |
| --- | --- | --- |
| Natives ZDS-Projekt | `libbsp`, interruptgesteuertes UART0; `Debug/camel_f91.lod`/`.hex` | Originalprojekt und Board-/ZDS-Debugging |
| Workspace-Builder | Eigener Polling-Adapter; `build/camelf91/camel.bin`/`.json`/`.map` | Reproduzierbare Regression und separater ZDS-Start |

Der vollständige Worttest führt alle **237 Wörterbuch-Einträge** aus und
enthält **201 Ergebnisprüfungen**. Die zusätzliche UART-Regression enthält
89 Fälle, jeweils vor und nach Systemreset.
[Worttest](camelf91-words.md), [Kit-Wörter](camelf91-kit.md).

## Checkout und nativer Build

```sh
sh scripts/setup-camelf91.sh
```

Das Setup initialisiert CAMEL und dessen BSP. Der BSP-Gitlink zeigt auf einen
öffentlichen `ez80f91bsp`-Stand; die frühere lokale SSH-URL und der ungültige
Symlink wurden ersetzt. Der ursprüngliche alte BSP-Commit war öffentlich
nicht abrufbar und ist nicht mehr Voraussetzung des aktuellen nativen Builds.

1. `libbsp/libbsp.zdsproj` in ZDS II 5.3.5 mit **Debug → Rebuild All** bauen.
2. `camel_f91.zdsproj` öffnen und **Debug** neu bauen.
3. Das RAM-Target mit Ethernet Smart Cable bzw. passendem Hardwaredebugger
   wählen, `Debug/camel_f91.lod` laden und mit F5 starten.

Alternativ nach Erzeugung der ZDS-Make-Datei:

```sh
make -C subprojects/CAMELF91_24
```

`ZDS_HOME`, `WINE` und `BUILD` sind überschreibbar. `_main` ruft nach
`init_bsp` explizit `init_uart0` für 115200 8N1 auf. Ohne diesen zusätzlichen
Aufruf initialisiert das aktuelle BSP nur die Board-Pins und die Konsole
bleibt leer. Das Debug-Target hat `externalAutoSelect=false`, da CS0 für
einen externen Flashbaustein in diesem RAM-Profil nicht freigegeben ist.

## Reproduzierbarer Polling-Build

```sh
python3 examples/camelf91/build.py --zds "$ZDS_HOME"
python3 tools/zds/f24.py --prepare-only
```

Der Builder liest die bekannten ASM-Dateien aus dem festgelegten historischen
Commit, wendet `patches/camelf91/0001-fix-24bit-core.patch` in einer Buildkopie
an und ergänzt die gemeinsamen Kit-Includes. Er akzeptiert im nativen
Checkout die ursprünglichen oder exakt korrigierten Kernfassungen sowie die
bekannte UART-Startup-Anpassung. Fremde Kernänderungen werden abgewiesen.
Lokale IDE-Einstellungen ändern das Polling-Image nicht.

`console.inc` deklariert die gemeinsame Konsolen-ABI. `poll_bsp.asm`
initialisiert UART0 und stellt `init_bsp`, `putc`, `getc` und `kbhit` ohne
UART-Interrupts bereit. `__cstartup=1` aktiviert die Original-BSS-/DATA-
Initialisierung. Die beiden Kit-Includes müssen im nativen Checkout und
unter `examples/camelf91/` identisch sein.

Die Metadaten speichern Basiscommit, Patch-/Quellhashes, Symboladressen und
Image-SHA256. Das aktuelle gespeicherte Polling-Image hat 10688 Bytes und
441 Bytes statischen RAM-Bedarf zuzüglich Forth-Stacks/Arbeitsbereichen.
Die Map weist 10691 ROM-Bytes einschließlich drei nicht ausgegebener
Reservierungsbytes aus.

## Speicher und Takt im geprüften Debugprofil

| Bereich | Verwendung |
| --- | --- |
| 000000h–07FFFFh | Externes SRAM als Code-/ROM-Bereich |
| B7D000h–BFFFFFh | Linker-RAM, interner RAM und hohes externes SRAM |
| C00000h | Oberes Stackende; erstes Push darunter |
| 800000h–800002h | Kit-Latches bei aktiviertem Kit und passendem CS2 |
| Systemtakt | 50-MHz-Oszillator, PLL aus |

Die Release-/Chiponly-Konfigurationen haben eigene Linker-/Targetdateien.
Die hier beschriebenen Tests betreffen das Debug-RAM-Profil.

## Verwenden und testen

```sh
python3 tools/zds/f24.py
python3 tests/test_camelf91.py "$QEMU_EZ80"
python3 tests/test_camelf91_words.py "$QEMU_EZ80"
python3 tests/test_camelf91_kit.py "$QEMU_EZ80"
```

```forth
1 2 + .
: QUADRAT DUP * ;
12 QUADRAT .
BUTTONS .
CHAR A MATRIX-CHAR
MATRIX-OFF
```

Der interaktive Starter öffnet ein getrenntes Projekt unter `build/f24/`.
[ZDS-Bedienung](start-f24.md) und [Kernanalyse](camelf91-analysis.md)
beschreiben Debuggerkommandos und die fünf korrigierten Fehlerbereiche.

## Herkunft

Die ursprünglichen CamelForth-Port-/Nutzungshinweise stehen weiterhin in
`ReadMe.txt`, `LICENSE` und den Quellköpfen des Teilprojekts. Sie werden durch
die Integration und die neuen Anleitungen nicht ersetzt.
[Quellen und Lizenzhinweise](licenses.md).
