# Historischer Meilenstein: ADL, Register, Stack und UART0

Die folgenden Einschränkungen beschreiben den ersten CPU-/UART-Stand vom
27.10.2026. Für den aktuellen Build und Funktionsumfang gelten
[Erste Schritte](getting-started.md) und [Status](status.md).

Erster CPU-/UART-Meilenstein; erweitert durch
[FreeRTOS-C-Startup und Speichersteuerung](freertos-boot.md).

Stand: 2026-10-27, QEMU v11.1.2, Entwicklungsbranch `ez80f91-dev`.
CPU `ez80f91`, Systemziel `ez80-softmmu`, Maschine `ez80f91-minimal`.

## Ergebnis

`examples/hello_uart0.bin` ist ein getestetes Raw-ROM von 107 Bytes. Es wechselt
vom Resetmodus nach ADL, setzt SPL, initialisiert UART0 und gibt exakt
`Hello eZ80F91\r\n` aus. Dabei werden CALL/RET, PUSH/POP, Speicherzugriffe
und Status-Polling verwendet. Anschließend hält die CPU mit HALT an.
Das ROM wurde vom beiliegenden Python-Generator erzeugt; die ASM-Datei ist
eine äquivalente, lesbare Darstellung und wurde nicht mit ZDS assembliert.

## Bauen und starten

Die Implementierung ist vollständig im äußeren Repository als
`patches/0001-ez80f91-minimal.patch` gesichert. Der QEMU-Checkout wird ignoriert.

```sh
git clone --depth 1 --branch v11.1.2 https://gitlab.com/qemu-project/qemu.git qemu
sh scripts/apply-qemu-patches.sh
mkdir -p build/ez80
cd build/ez80
../../qemu/configure --target-list=ez80-softmmu --disable-docs --disable-werror --without-default-features --enable-tcg --enable-system --disable-tools
ninja -j8 qemu-system-ez80
cd ../..
python3 tests/test_smoke.py build/ez80/qemu-system-ez80
python3 tests/test_cpu_uart.py build/ez80/qemu-system-ez80
build/ez80/qemu-system-ez80 -M ez80f91-minimal -bios examples/hello_uart0.bin -display none -monitor none -serial mon:stdio
```

Mit Ctrl-A X wird QEMU bei `-serial mon:stdio` beendet. HALT beendet den
Emulator nicht. Alternativ `-serial file:/tmp/uart0.txt -monitor stdio`
verwenden; im Monitor zeigen `info registers` den CPU-Zustand und `quit`
beendet QEMU. Das Empfangstestprogramm benötigt einen lokalen Unix-Socket.

Das Beispiel kann ohne SDK neu erzeugt werden:

```sh
python3 examples/make_hello_uart0.py /tmp/hello_uart0.bin
```

Build dieser Sitzung: `/tmp/qemuez80f91-build-baseline/qemu-system-ez80`.
Dieser Build wurde nach dem AVR-Werkzeugtest auf ez80-softmmu umgestellt.
Das aktuelle Buildprotokoll ist `/tmp/qemuez80f91-build.log` (temporär).

## Unterstützte CPU-Teilmenge

| Bereich | Implementiert |
| --- | --- |
| Modi | SIS/SIL/LIS/LIL; persistente Wechsel mit JP und gemischtem CALL/RET |
| Register | LD rr,nn für BC/DE/HL/SP und IX/IY; LD r,n; LD r,r; EX DE,HL |
| Speicher | LD r,(HL), LD (HL),r/n; LD A,(nn), LD (nn),A; LD HL,(nn), LD (nn),HL |
| Stack | PUSH/POP BC/DE/HL/AF/IX/IY; SPS/SPL; LD SP,HL/IX/IY |
| Kontrolle | JP nn/(HL)/(IX)/(IY), JR und JR NZ/Z/NC/C; CALL/RET |
| Weitere | INC/DEC rr und IX/IY; NOP/HALT/DI; AND/OR/XOR n, XOR A, OR A, CP n |
| I/O | IN0 r,(n), OUT0 (n),r; LD MB,A, LD A,MB; STMIX/RSMIX |

Es ist weiterhin nur eine Teilmenge des eZ80-Befehlssatzes. Nicht aufgeführte
Befehle und nicht unterstützte Präfixkombinationen führen zu einer Diagnose
mit PC und Opcode und Fehlerstatus. LD I,HL und LD HL,I sind inzwischen implementiert. Der Flagwiderspruch
bei LD HL,I bleibt dokumentiert: [Erweiterte Opcodes](extended-opcodes.md).

Bei kurzen Multibyte-Registerschreibzugriffen wählt der Emulator für die laut
Handbuch undefinierten oberen Bytes deterministisch null. Definierte einzelne
Bytezugriffe auf B/C usw. erhalten die übrigen Bytes. Präfixe für gewöhnliche
Datenoperationen ändern ADL nicht dauerhaft. LD MB,A ist im Z80-Modus ein NOP.
Gemischte CALL-/RET-Frames setzen in dieser Implementierung MADL=1 voraus;
RET.S wird abgelehnt. Markerbytes und getrennte Stacks folgen UM0077
S. 115–116 und 292–293.

Der gemeinsame Decoder erzeugt einen TCG-Helferaufruf pro Befehl; die
Helfer implementieren die dekodierten Seiteneffekte ohne eigene CPU-Schleife.
Ein Block enthält vorerst einen Befehl. Nahe dem 16-/24-Bit-Adressende liest
ein Helfer genau einen Befehl zur Laufzeit mit demselben Decoder: QEMUs
allgemeiner Übersetzerzugriff verlangt virtuell zusammenhängende Seiten.
Dieser Pfad vermeidet falsche Codeabhängigkeiten beim Adress-Wrapping.
I/O-Grenzen sind auch für `-icount shift=0` gesetzt. Das ist keine Zusage
zyklusgenauer Ausführung. Während HALT werden keine Refreshzyklen simuliert.

## Speicher und UART0

Festes Resetabbild: Flash 000000–03FFFF, EMAC-RAM FFC000–FFDFFF,
allgemeines RAM FFE000–FFFFFF. Dies ist die Resetbelegung;
registergesteuertes Remapping ist inzwischen implementiert. Flash bleibt
schreibgeschütztes ROM, Programmieren/Löschen fehlt.

UART0 ist ein separates QOM-Gerät am QEMU-I/O-Adressraum, angebunden an
`-serial`. Implementiert sind die Register C0–C7 mit DLAB-Umschaltung,
Baudteilerspeicherung, Scratchregister und funktionalem Senden/Empfangen.
RBR-Lesen löscht DR. IN0 setzt die dokumentierten Flags und erhält Carry.

Für die UART-Pinfreigabe werden PD_DDR/ALT1/ALT2 (A3–A5) gespeichert:
Mode 7 erfordert DDR=1, ALT1=0, ALT2=1. PD0 steuert TX, PD1 RX.
CLK_PPD1 (DB) sperrt bei Bit 0 UART0 und bei Bit 7 die Port-D-Anbindung.
Diese Register bilden nur den für UART0 nötigen Teil der GPIO-/Taktlogik ab.
Vollständige GPIO-Pins, andere Peripherietakte und elektrische Pegel fehlen.
Quellen: PS0192 S. 47, 50–51 und 182–194.

Das UART-Modell ist ausdrücklich funktional: TX erfolgt synchron, LSR meldet
THRE/TEMT bereit, RX hat einen Zeichenpuffer. Baudteiler und 8N1-Konfiguration
werden gespeichert, Baudtiming wird nicht simuliert. FIFO, Interrupts,
Modemsteuerung und Loopback sind nicht implementiert; entsprechende
Anforderungen werden über `-d unimp` protokolliert. Firmware muss vorerst
Polling mit deaktivierten FIFOs und UART-Interrupts verwenden.

## Validierung

Alle Integrationstests dieses Standes bestanden:

- Reset, NOP/HALT, Haltzustand, Systemreset und erneute ROM-Ausführung.
- Leere/zu große ROMs; illegale Instruktionen werden separat als Hardware-TRAP getestet.
- 16-/24-Bit-Register, alle vier Breitenpräfixe und Indexregister-Stackzugriffe.
- SPS/SPL mit MBASE, kurze und lange Stacküberschreibungen in beiden Modi.
- CALL/RET in Z80 und ADL, gemischte Frames und Rücksprung mit oberem Adressbyte.
- Bytegenaue Stackinhalte, AF-Nullbyte, 24-Bit-Speichertransfer ohne viertes Byte.
- 64-KiB-Befehls-Wrapping, linearer ADL-Übergang und 24-Bit-Code-/Stack-Wrapping.
- JP über Register mit Moduswechsel; LD MB,A bleibt im Z80-Modus wirkungslos.
- Exakte UART-Ausgabe unter icount, DLAB ohne Zeichenleck, Pinmux und Taktsperren.
- Empfang vom Unix-Socket, DR-Löschung und UART-Resetwerte.
- Separates Hello-ROM mit realer Textschleife und Unterprogrammaufrufen.
- Interaktiver Start mit mon:stdio und Beenden über Ctrl-A X.
- Aktualisierter Patch auf sauberem Basischeckout erfolgreich angewendet.
- QEMU-Checkpatch ohne Fehler (ohne Sign-off-Prüfung); verbleibend ist nur
  der Hinweis auf einen Maintainer-Eintrag für eine spätere Upstream-Einreichung.

Migration bleibt gesperrt. Gast-GDB-Registerzugriff und Ethernet-ZDI sind
inzwischen eingerichtet: [ZDS-Anbindung](zds-ethernet.md).
Timer0 und Interruptannahme sind inzwischen implementiert; siehe
[Timer/Vektoren](timer0-interrupts.md). Weitere Geräte und Befehle bleiben offen.
Ein vollständiger F91-Kompatibilitätsnachweis liegt noch nicht vor.
Weitere Regressionen: `tests/test_memory.py`, `tests/test_cstartup_ops.py`
und `tests/test_zds_cstartup.py`.

Der echte Kernel-Scheduler mit zwei präemptiven Tasks ist inzwischen ebenfalls
geprüft: [FreeRTOS-Tasks](freertos-tasks.md), `tests/test_freertos_tasks.py`.

Weitere Kernelproben prüfen freiwilligen Yield, kritische Verschachtelung,
Delay/Idle und Ticküberlauf: [Kernelpfade](freertos-blocking.md),
`tests/test_freertos_blocking.py`.

Der unveränderte Original-Boardstart mit Oszillator- und PLL-Variante ist
ebenfalls geprüft: [Boardstart/PLL](board-startup.md),
`tests/test_board_startup.py` und `tests/test_pll.py`.

CAMELF91_24 ist als festes Sub-/Testprojekt eingebunden und per UART geprüft:
[CamelForth](camelf91.md), `tests/test_camelf91.py`.
