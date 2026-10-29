# qemuez80f91

Entwicklungsumgebung für den **Zilog eZ80F91**: QEMU-Systememulation,
ZDS-II-Debugging, CamelForth und FreeRTOS mit Ethernet, CP/M und
Development-Kit-Anzeige.

Der Emulator führt echte eZ80-Firmware in Z80- und ADL-Modi aus. Der
Schwerpunkt liegt auf funktionalem Verhalten und überprüfbaren Regressionen.
Er ist keine takt- oder busgenaue Simulation und kein vollständiger
Kompatibilitätsnachweis für den eZ80F91.

## Projekte

| Bestandteil | Aufgabe | Einstieg |
| --- | --- | --- |
| QEMU/eZ80F91 | CPU, Speicher, Flash, UART, Timer, RTC, Ethernet und Kit | [Architektur](docs/architecture.md), [Build](docs/getting-started.md) |
| CAMELF91_24 | 24-Bit-Forth mit korrigiertem Kern, Tastern und 5×7-Matrix | [Projekt-README](https://github.com/notwendig/CAMELF91_24), [Forth-Anleitung](docs/camelf91.md) |
| ez80f91bsp | Assembler-Bibliothek für das native CAMEL-Projekt | [BSP-README](https://github.com/notwendig/ez80f91bsp) |
| FreeRTOS-eZ80f91 | FreeRTOS, TCP/IP, CP/M 2.2 und Kit-Demo | [Projekt-README](https://github.com/notwendig/FreeRTOS-eZ80f91), [Build](https://github.com/notwendig/FreeRTOS-eZ80f91/blob/master/BUILD.md) |
| ZTP TCPUDPDemo | Build und Betrieb des installierten Herstellerbeispiels | [TCP/UDP-Anleitung](docs/ztp-tcpudp.md) |
| Debugger und Tests | Ethernet Smart Cable, Scan Device, Test-ROMs und Regressionen | [ZDS II](docs/zds-ethernet.md), [Tests](docs/testing.md) |

## Schnellstart

```sh
git clone https://github.com/notwendig/qemuez80f91.git
cd qemuez80f91
git submodule update --init -- subprojects/CAMELF91_24 subprojects/FreeRTOS-eZ80f91
```

QEMU wird aus der festgelegten Basis mit dem mitgelieferten Patch gebaut:

```sh
git clone --depth 1 --branch v11.1.2 https://gitlab.com/qemu-project/qemu.git qemu
sh scripts/apply-qemu-patches.sh
mkdir -p build/ez80
cd build/ez80
../../qemu/configure --target-list=ez80-softmmu --disable-docs --disable-werror --without-default-features --enable-tcg --enable-system --disable-tools
ninja -j8 qemu-system-ez80
cd ../..
export QEMU_EZ80="$PWD/build/ez80/qemu-system-ez80"
python3 tests/test_smoke.py "$QEMU_EZ80"
```

[Voraussetzungen und erster Start](docs/getting-started.md) erläutert die
Werkzeuge, den Betrieb ohne Netzwerk und die optionale ZDS-Installation.

## Bedienung

```sh
./start.sh                 # UART-Terminal; CPU wartet auf ZDS II
./start.sh --kit           # zusätzlich Kit-Fenster mit Matrix und Tastern
./start.sh --run --kit     # gespeichertes Flash direkt starten
./start.sh dbgport 4041    # separate Instanz auf anderem Debugport
```

Diese Starter verwenden die vorhandene Netzwerkbridge `br0`. Sie richten
keinen DHCP-Server ein; im vorgesehenen Netz liefert die **nadibox** DHCP.
Die CPU wird erst nach Freigabe des TAP-Ports gestartet.
Ein ROM kann alternativ ohne Bridge direkt ausgeführt werden:

```sh
"$QEMU_EZ80" -M ez80f91-minimal -bios examples/hello_uart0.bin \
  -display none -monitor none -serial mon:stdio -nic none
```

Strg-A, X beendet den direkten QEMU-Aufruf. Beim Starter beendet Strg-C im
UART-Terminal die Instanz und speichert deren Flash.

### CamelForth

```sh
python3 tools/zds/f24.py
```

Der Starter erzeugt eine eigene Buildkopie und öffnet ZDS II mit
Quellcode-Debugging. Nach **F5** steht die Forth-Konsole bereit:

```forth
1 2 + .
BUTTONS .
CHAR A MATRIX-CHAR
MATRIX-OFF
```

[ZDS-Start](docs/start-f24.md), [Kit-Wörter](docs/camelf91-kit.md),
[Worttest](docs/camelf91-words.md). Das Wörterbuch umfasst 237 Wörter;
der vollständige Worttest enthält 201 Ergebnisprüfungen. Zusätzlich prüfen
89 Regressionsfälle das Image vor und nach Reset.

### FreeRTOS und ZTP

```sh
python3 subprojects/FreeRTOS-eZ80f91/setup-dependencies.py
python3 -m tools.demo --prepare-only
```

FreeRTOS wird anschließend im ZDS-Projekt `EZ80F910300ZCOG.zdsproj`,
Konfiguration **Debug**, gebaut. `python3 -m tools.demo` startet das
installierte ZTP-TCP/UDP-Beispiel. Beide benötigen die passende
[ZDS-/Netzwerkkonfiguration](docs/getting-started.md).

## Daten und Konfiguration

- `QEMU_EZ80`: Pfad zum gebauten Emulator.
- `ZDS_HOME`: ZDS II, standardmäßig `~/.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5`.
- Debugger: TCP 4040, Scan Device: UDP 3000. Die Debuggeradresse ist die
  Hostadresse, nicht die vom Gast per DHCP bezogene IP.
- Laufzeitprotokolle und QMP-Socket: `/tmp/ez80f91-<uid>/<port>.*`.
- Persistentes Flash: `ez80f91_0.<port>` sowie externe Images im aktuellen
  Arbeitsverzeichnis. Diese Dateien sind Nutzdaten und werden nicht eingecheckt.
- `build/`: lokale Buildprodukte und Berichte; `examples/`: bewusst versionierte
  Quellen und kleine Test-Images mit Metadaten.

## Dokumentation und Entwicklungsstand

[Dokumentationsübersicht](docs/README.md) · [Status und Grenzen](docs/status.md) ·
[Entwicklung und Repositorypflege](docs/development.md) ·
[Quellen und Lizenzhinweise](docs/licenses.md)

Die QEMU-Änderungen werden in `patches/0001-ez80f91-minimal.patch` gepflegt.
Der lokale QEMU-Checkout und Hersteller-SDKs gehören nicht zum veröffentlichten
Quellbestand. Die Teilprojekte besitzen eigene Git-Historien und Lizenzhinweise.
