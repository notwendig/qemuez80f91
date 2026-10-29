# QEMU-Basis

## Festgelegter Quellstand

| Eigenschaft | Wert |
| --- | --- |
| Upstream | `https://gitlab.com/qemu-project/qemu.git` |
| Release | `v11.1.2` |
| Basiscommit | `4fc49f46dc95d4a27de2509e7fceb2931e91faeb` |
| Systemziel | `ez80-softmmu` |
| CPU | `ez80f91` |
| Maschinen | `ez80f91-minimal`, `ez80f91-freertos` |
| Entwicklungsstand | `patches/0001-ez80f91-minimal.patch` im Workspace |

Der lokale Checkout `qemu/` ist ein ignoriertes, separates Git-Repository.
Er darf auf einem Entwicklungsbranch stehen; sein Upstream-Remote ist kein
Push-Ziel der Workspace-Veröffentlichung. Der vollständige eZ80-Stand wird
als Patch dieses Projekts verteilt.

## Reproduzieren

```sh
git clone --depth 1 --branch v11.1.2 https://gitlab.com/qemu-project/qemu.git qemu
sh scripts/apply-qemu-patches.sh
mkdir -p build/ez80
cd build/ez80
../../qemu/configure --target-list=ez80-softmmu --disable-docs --disable-werror --without-default-features --enable-tcg --enable-system --disable-tools
ninja -j8 qemu-system-ez80
./qemu-system-ez80 --version
```

Beim ersten Konfigurieren kann QEMU seine festgelegten Build-Unterprojekte
und Python-Abhängigkeiten laden. `--disable-download` funktioniert erst,
wenn diese vorhanden sind. Ein Configure-Fehler ist vor dem Kompilieren zu
beheben; keine fremden Dateien aus einer anderen QEMU-Version übernehmen.

`apply-qemu-patches.sh` prüft die Basis und akzeptiert einen bereits
angewendeten identischen Patch. Für eine bestehende Entwicklungskopie siehe
[Repositorypflege](development.md). Buildverzeichnisse werden außerhalb des
Quellbaums geführt.

## Integration

`target/ez80/` enthält Registerzustand, Decoder, TCG und GDB-Schnittstelle;
`hw/ez80/` CPU-Anbindung, Maschinenprofile und F91-Geräte. Die Architektur
ist in den QEMU-Kconfig-/Meson-Listen registriert. Ein 32-Bit-Hostwert macht
die Gastregister nicht zu 32-Bit-Registern: die architektonischen Breiten
bleiben 8, 16 oder 24 Bit.

Der TCG-Pfad verwendet einen dekodierten Gastbefehl pro Block. Er ersetzt
keine hardwaregetreuen Befehlslaufzeiten oder elektrische Bussimulation.
Das ursprüngliche AVR-Basisbuild war nur eine Werkzeugprüfung;
die heutigen F91-Nachweise stehen im [Testkatalog](testing.md).

## Lokale Werkzeuge und Grenzen

Der Entwicklungsbuild wurde mit GCC, Python 3, Ninja, pkg-config und GLib
geprüft. Die Configure-Ausgabe benennt die für den jeweiligen Host tatsächlich
verwendeten Versionen. Auf dem Entwicklungsrechner liegt zusätzlich ein
Build unter `/tmp/qemuez80f91-build-baseline`; andere Rechner sollten
`QEMU_EZ80` explizit auf ihren eigenen Build setzen.

Die vollständige [Architektur](architecture.md) beschreibt Geräte und
Debugger. [Status](status.md) benennt die funktionalen Grenzen; ein
bestehender Build ist kein vollständiger eZ80F91-Kompatibilitätsnachweis.
