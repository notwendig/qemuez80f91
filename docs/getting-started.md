# Erste Schritte

## Voraussetzungen

Für den Emulator: Linux, Git, C-Compiler, Python 3, Ninja, pkg-config und die
von QEMUs Configure-Prüfung angeforderten Entwicklungsbibliotheken, insbesondere
GLib. QEMU richtet Meson und seine Python-Buildumgebung beim Konfigurieren ein.
Der genaue geprüfte Quellstand steht in [QEMU-Basis](qemu-base.md).

Die lokalen Test-ROMs benötigen überwiegend nur Python und den Emulator.
Einige Decoder-/Dekompressionstests übersetzen zusätzlich kleine Hostprogramme
mit `cc`. Die Skripte sind direkt aufzurufen; sie sind keine pytest-Suite.

Zusätzlich für die Hersteller-Firmware und ZDS-Integration:

- installierte **ZDS II eZ80Acclaim! 5.3.5** samt ZTP 2.5.1;
- Wine mit Zugriff auf diese Installation;
- Nexus SDK 1.1 und `i686-w64-mingw32-gcc` für die originalen DLL-Integrationstests;
- Tkinter für das Kit-Fenster; `gnome-terminal` oder `xterm` für `start.sh`.

SDKs werden vom jeweiligen Hersteller bezogen und nicht im Repository verteilt.

## Checkout und QEMU-Build

```sh
git clone https://github.com/notwendig/qemuez80f91.git
cd qemuez80f91
git submodule update --init -- subprojects/CAMELF91_24 subprojects/FreeRTOS-eZ80f91
git clone --depth 1 --branch v11.1.2 https://gitlab.com/qemu-project/qemu.git qemu
sh scripts/apply-qemu-patches.sh
mkdir -p build/ez80
cd build/ez80
../../qemu/configure --target-list=ez80-softmmu --disable-docs --disable-werror --without-default-features --enable-tcg --enable-system --disable-tools
ninja -j8 qemu-system-ez80
cd ../..
export QEMU_EZ80="$PWD/build/ez80/qemu-system-ez80"
```

`apply-qemu-patches.sh` verlangt den festgelegten Upstream-Basiscommit und
akzeptiert einen bereits angewendeten identischen Patch. Ein vorhandener
Entwicklungsbranch mit eigenen Commits wird nicht automatisch zurückgesetzt.
Für solche Checkouts gilt der [Entwicklungsablauf](development.md).

## Erster Test ohne Netzwerk

```sh
python3 tests/test_smoke.py "$QEMU_EZ80"
python3 tests/test_cpu_uart.py "$QEMU_EZ80"
"$QEMU_EZ80" -M ez80f91-minimal -bios examples/hello_uart0.bin \
  -display none -monitor none -serial mon:stdio -nic none
```

Erwartete Ausgabe: `Hello eZ80F91`. Danach hält die Gast-CPU an; QEMU bleibt
geöffnet. Strg-A, X beendet den Prozess. Die Tests benötigen lokale Sockets.

## ZDS und Firmware bauen

```sh
export ZDS_HOME="$HOME/.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5"
sh scripts/setup-camelf91.sh
python3 examples/camelf91/build.py --zds "$ZDS_HOME"
python3 tools/zds/f24.py --prepare-only
```

Der Polling-Build kopiert die festgelegten Kernquellen und wendet die
mitgelieferten Korrekturen an. Die gemeinsamen Kit-Includes werden in das
Image eingebunden. Für das native CAMEL-Projekt zuerst `libbsp.zdsproj`
im Unterordner `libbsp/` in ZDS bauen, danach `camel_f91.zdsproj`.
Details: [CamelForth](camelf91.md).

FreeRTOS besitzt einen eigenen [Setup-/Buildablauf](https://github.com/notwendig/FreeRTOS-eZ80f91/blob/master/BUILD.md).
Das ZTP-Demo verwendet das installierte Herstellerbeispiel und baut eine
getrennte Kopie: [TCP/UDP](ztp-tcpudp.md).

## UART, Netzwerk und Kit

`./start.sh --kit` öffnet UART und Development-Kit-Fenster; die CPU wartet
auf ZDS. `--run` startet direkt aus persistentem Flash. `QEMU_EZ80` muss auf
den gerade gebauten Emulator zeigen. Historischer Fallbackpfad des Starters
ist `/tmp/qemuez80f91-build-baseline/qemu-system-ez80`.

Der Starter erwartet eine existierende Bridge `br0` und einen dafür
konfigurierten QEMU-Bridge-Helper. Er verändert weder die Host-Bridge noch
deren DHCP-Konfiguration. Im vorgesehenen Netz liefert nadibox
`192.168.77.1` die Leases. Für andere Umgebungen unterstützen die
[Demo-Werkzeuge](ztp-tcpudp.md) explizite Bridge-/Serverparameter.

Debugger TCP 4040 und Discovery UDP 3000 sind vom Gast-Ethernet unabhängig.
Ein zweiter Debugger auf demselben Port wird abgewiesen. Weitere Instanzen
verwenden beispielsweise `./start.sh dbgport 4041`.

## Häufige Ursachen

| Symptom | Prüfung |
| --- | --- |
| Starter findet QEMU nicht | `QEMU_EZ80` auf das gebaute Binary setzen. |
| Kein UART-Banner | Gast in ZDS mit F5 fortsetzen; passendes RAM-/Flash-Target laden. |
| DTL-Schreibfehler ab 100000h beim CAMEL-Debugstart | Debug-Target mit abgeschalteter externer Flash-Erkennung verwenden. |
| Kit bleibt dunkel | Mit `--kit` starten; CS2 muss 800000h abdecken; Firmware muss die Matrix ansteuern. |
| Kein DHCP | TAP-Port muss forwarding sein; Bridge, nadibox und Gast-PHY-Adresse prüfen. |
| Eine Korrektur ist noch nicht sichtbar | QEMU und ggf. Kit-Fenster neu starten; laufende Prozesse laden neue Dateien nicht automatisch. |

Flash-Dateien im Arbeitsverzeichnis enthalten den gespeicherten Gastzustand.
Sie gehören nicht zu einem Cache und dürfen beim Aufräumen nicht pauschal
gelöscht werden.
