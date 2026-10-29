# Entwicklung und Repositorypflege

## Repositorystruktur

| Pfad | Inhalt und Versionsführung |
| --- | --- |
| `docs/` | Aktuelle Betriebsanleitungen, Architektur und Implementierungsnachweise |
| `patches/0001-ez80f91-minimal.patch` | Vollständiger QEMU-Entwicklungsstand gegenüber der Basis |
| `qemu/` | Ignorierter lokaler QEMU-Checkout; Änderungen in den Patch übernehmen |
| `subprojects/CAMELF91_24/` | Eigenes Git-Submodul; darin `libbsp/` als verschachteltes Submodul |
| `subprojects/FreeRTOS-eZ80f91/` | Eigenes Git-Submodul mit Kernel-, Netzwerk- und uzlib-Abhängigkeiten |
| `examples/` | Reproduktionsquellen und bewusst gespeicherte kleine Test-Images |
| `tests/` | Direkt ausführbare Prüfskripte; Sonderanforderungen im Testkatalog |
| `tools/`, `scripts/` | Starter, Debuggerbrücke, Build-/Setup-Helfer |
| `build/` | Ignorierte Buildprodukte und Berichte |

## QEMU ändern

Die Basis ist Commit `4fc49f46dc95d4a27de2509e7fceb2931e91faeb`.
Entwicklungscommits im lokalen QEMU-Checkout sind möglich. Nach Änderungen
muss der Gesamtpatch auch den Arbeitsbaum enthalten:

```sh
git -C qemu diff --binary 4fc49f46dc95d4a27de2509e7fceb2931e91faeb > patches/0001-ez80f91-minimal.patch
git -C qemu apply --reverse --check ../patches/0001-ez80f91-minimal.patch
ninja -C build/ez80 -j8 qemu-system-ez80
```

Neue QEMU-Dateien müssen zunächst im dortigen Index bekannt sein, damit
`git diff` sie erfasst. Fremde lokale Änderungen nicht pauschal zurücksetzen.
Die Vorwärtsprüfung erfolgt zusätzlich in einem unveränderten Basischeckout.
QEMU-Patches werden über dieses Projekt veröffentlicht, nicht in den
konfigurierten QEMU-Upstream gepusht.

## Firmwarequellen und generierte Dateien

CAMELs gemeinsamer Kit-Treiber liegt unter `examples/camelf91/kit.inc` und
für den nativen Build identisch unter `subprojects/CAMELF91_24/asm/`.
`kit_font.py` erzeugt den Zeichensatz; `word_tests.py` erzeugt die ladbare
Forth-Testdatei. Der Builder kontrolliert die gemeinsamen Quellen und
schreibt Image-/Quellhashes in `camel.json`.

Bei einer Änderung gespeicherter Test-Images gehören `.bin`, `.json` und
`.map` zusammen. Diese Dateien sind Testfixtures und werden nicht als
überflüssige Buildprodukte gelöscht. SDK-Ausgaben, Listings, Objekte und
IDE-Sitzungen bleiben dagegen in den ignorierten Buildverzeichnissen.

## Aufräumen

Entfernbar sind Python-/Lint-Caches, temporäre Berichte und nach Prüfung
nicht mehr benötigte Buildkopien. Vor dem Entfernen eines doppelten Git-
Checkouts müssen Arbeitsbaum, HEAD und Herkunft mit dem verbleibenden
Checkout verglichen werden. Ein ungeprüftes `git clean -xfd` ist hier
ungeeignet: Es würde auch lokale SDK-/Builddaten oder Flash-Nutzdaten erfassen.

Erhalten bleiben insbesondere:

- Flash-Images `ez80f91_*.<port>` und aktuelle Laufzeitprotokolle;
- verwendete ZDS-Projekt-/Target-/Linkerdateien;
- Testfixtures und deren Metadaten;
- Herstellerunterlagen, ursprüngliche Lizenzhinweise und Firmwarequellen.

Die ehemaligen chronologischen Sitzungsnotizen wurden durch
[Status](status.md), [Tests](testing.md) und die projektbezogenen Anleitungen
ersetzt. Sie sind bei Bedarf in der Git-Historie verfügbar.

## Commit und Push

Abhängigkeiten werden vor ihren Eltern veröffentlicht: BSP vor CAMEL,
Bibliotheken vor FreeRTOS und beide Firmwareprojekte vor dem Hauptprojekt.
Danach werden die passenden Gitlinks im Hauptrepository committed. So
verweist ein veröffentlichter Commit auf erreichbare Quellstände.

```sh
git status --short
git diff --check
git submodule status --recursive
```

[Tests](testing.md), Dokumentationslinks und Fixture-Hashes vor dem Commit
prüfen. Änderungen gezielt stagen, damit Flash-Dateien, SDKs, Cachedateien
und Zugangsdaten nicht versehentlich veröffentlicht werden. Ohne Force-Push
arbeiten; bei neuen Remote-Commits zuerst deren Verhältnis zum lokalen Stand
prüfen.
