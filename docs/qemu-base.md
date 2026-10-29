# QEMU-Basis und CPU-Anbindung

## Festgelegte Basis

- Upstream: https://gitlab.com/qemu-project/qemu.git
- Release: v11.1.2
- Commit: 4fc49f46dc95d4a27de2509e7fceb2931e91faeb
- Lokaler Checkout: `qemu/`, inzwischen mit lokalem eZ80-Entwicklungspatch.
- Releasequelle: https://www.qemu.org/download/

Der Checkout ist ein separates, flach geklontes Git-Repository und wird vom
äußeren Projekt ignoriert. Er ist kein Submodul. Für die Entwicklung werden
Änderungen dort auf einem eigenen Branch geführt; der obige Commit bleibt
die Vergleichsbasis. Fremde CPU-Kerne sind noch nicht übernommen.

## Entscheidung: reguläres TCG-Ziel

Wir implementieren `ez80-softmmu` als eigenes Systemziel mit TCG.
Geplanter CPU-Typ: `ez80f91`; geplante Maschine: `ez80f91-minimal`.
Diese Namen sind inzwischen registriert; siehe [Erste Ausführung](first-execution.md).

TCG übersetzt eZ80-Befehle in QEMU-Zwischencode. So bleiben CPU-Ausführung,
virtuelle Zeit, Interrupts und Debugging im üblichen QEMU-Ausführungspfad.
Ein unabhängiger Interpreter würde zusätzlich eine eigene Ausführungsschleife
und deren Integration benötigen. Für die erste Ausbaustufe wird kein solcher
Interpreter eingebettet. TCG allein bedeutet keine Takt- oder Busgenauigkeit.

Das vorhandene AVR-Ziel dient als überschaubares Beispiel für die APIs
von QEMU 11.1.2, nicht als Vorlage für eZ80-Befehlssemantik oder Speicherlayout.
AVR hat getrennte Code-/Datenzugriffe; diese Besonderheit wird nicht übernommen.

## Konkrete Integrationspunkte im geprüften Quellbaum

| Neue / anzupassende Datei | Zweck |
| --- | --- |
| `configs/targets/ez80-softmmu.mak` | Architektur, 32-Bit-QEMU-Repräsentation, Systemziel |
| `configs/devices/ez80-softmmu/default.mak` | Minimale Maschinenauswahl |
| `target/ez80/{Kconfig,meson.build}` | CPU-Buildquellen |
| `target/{Kconfig,meson.build}` | Architektur registrieren |
| `target/ez80/{cpu.h,cpu.c,cpu-param.h}` | CPU-Zustand, QOM, Reset, Adressraum |
| `target/ez80/{translate.c,helper.c}` | Decoder, TCG und Hilfsfunktionen |
| `hw/ez80/{Kconfig,meson.build}` und Elternlisten | Maschine und SoC einbinden |
| `hw/ez80/ez80f91.c` | Flash, RAM, I/O-Dekodierung, UART-Anbindung |

Weitere Integrationsstellen wie Debugger, Migration und Disassembler werden
mit dem CPU-Gerüst geprüft und nur mit tatsächlich implementiertem Verhalten
aktiviert. Ein vorhandenes QEMU-UART-Modell wird vor Wiederverwendung auf
F91-Registersemantik, FIFO und Seiteneffekte geprüft.

QEMU-interne Register und Adressberechnungen können 32 Bit verwenden;
architektonische Breiten bleiben ausdrücklich 8/16/24 Bit. Ein 32-Bit-Target
macht den Gast nicht zu einer 32-Bit-CPU. 24-Bit-Zugriffe müssen korrekt über
Bytezugriffe abgebildet werden; eine pauschale 32-Bit-Last wäre falsch.

`target/avr/cpu.c` zeigt in dieser Version `TCGCPUOps` mit
`get_tb_cpu_state`, `translate_code`, `restore_state_to_opc`, `mmu_index`
und `tlb_fill`. Diese aktuellen Schnittstellen sind die Arbeitsgrundlage.
ADL und weitere decoderrelevante Zustände müssen in der Translation-Block-
Identität berücksichtigt werden. Änderungen an ADL/MBASE benötigen passende
Blockgrenzen; Präfixe gelten entsprechend der CPU-Spezifikation.
Speicherzugriffe müssen über QEMU laufen, damit Remapping und geänderter
Programmcode keine veralteten Übersetzungen hinterlassen.

## Reproduzierbarer Basisbuild

Der erste Build verwendet das unveränderte AVR-Systemziel als Werkzeugtest.
Er ist kein eZ80-Emulator und kein Test der F91-Semantik.

```sh
git clone --depth 1 --branch v11.1.2 https://gitlab.com/qemu-project/qemu.git qemu
git -C qemu rev-parse HEAD
mkdir -p build/baseline
cd build/baseline
../../qemu/configure --target-list=avr-softmmu --disable-docs --disable-werror --without-default-features --enable-tcg --enable-system --disable-tools
ninja -j2 qemu-system-avr
./qemu-system-avr --version
./qemu-system-avr -machine help
```

Beim ersten Konfigurieren lädt QEMU die festgelegten Unterprojekte und
Python-Buildabhängigkeiten. Ein direktes `--disable-download` funktioniert
erst, wenn diese vorhanden sind. Meson wird über QEMUs Python-Umgebung
bereitgestellt; eine systemweite Meson-Installation ist nicht erforderlich.

Geprüfte Hostwerkzeuge: GCC 16.2.1, Python 3.14.8, Ninja, pkg-config,
GLib 2.88.4 und Pixman 0.46.2. Der tatsächlich ausgeführte Basisbuild liegt
außerhalb des Repositories in `/tmp/qemuez80f91-build-baseline`.
Ergebnis am 2026-10-27:

- Konfiguration erfolgreich, Meson 1.11.1 aus QEMUs Python-Umgebung.
- `ninja -j2 qemu-system-avr`: erfolgreich kompiliert und gelinkt.
- `./qemu-system-avr --version`: QEMU emulator version 11.1.2 (v11.1.2).
- `./qemu-system-avr -machine help`: erfolgreich; Arduino-Modelle und `none`.
- Upstream-Checkout nach dem Build ohne getrackte Änderungen.
- Buildprotokoll: `/tmp/qemuez80f91-baseline-build.log` (temporär).

Der erste Sandbox-Build wurde durch einen schreibgeschützten Compiler-Cache
abgebrochen. Derselbe Build lief mit freigegebenem Cachezugriff erfolgreich.
Es waren keine Quellcodeanpassungen für GCC 16 oder Python 3.14 nötig.
Ein F91-ROM wurde in dieser Stufe noch nicht ausgeführt.

## Nächster Implementierungsschritt

Das Gerüst wurde um ADL-, Register-/Stackbefehle und funktionales UART0
erweitert; das Hello-ROM ist erfolgreich getestet. Siehe [Erste Ausführung](first-execution.md).
Speichersteuerregister und ZDS-C-Startup sind inzwischen geprüft;
Details: [FreeRTOS-C-Startup](freertos-boot.md). Als Nächstes den
vollständigen Startpfad sowie Interrupts und Timer0 ergänzen.
Nicht implementierte Befehle müssen mit PC und Opcode diagnostiziert werden.
