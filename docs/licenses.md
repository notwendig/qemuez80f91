# Herkunft und Lizenzhinweise

Dieses Workspace kombiniert eigenständige Projekte und Testartefakte.
Es ersetzt deren Lizenzdateien und Quellkopfhinweise nicht durch eine
pauschale Workspace-Lizenz.

| Bestandteil | Herkunft und maßgebliche Hinweise |
| --- | --- |
| QEMU und eZ80-Integration | Festgelegtes [QEMU-Upstream](qemu-base.md); Lizenzdateien des Quellbaums und SPDX-/Quellkopfhinweise der einzelnen Dateien |
| CAMELF91_24 | [notwendig/CAMELF91_24](https://github.com/notwendig/CAMELF91_24); `LICENSE`, ursprüngliche `ReadMe.txt` und Quellköpfe. Das Original enthält gesonderte CamelForth-Nutzungshinweise. |
| ez80f91bsp | [notwendig/ez80f91bsp](https://github.com/notwendig/ez80f91bsp); vorhandene Quellkopfhinweise. Es wird keine zusätzliche Lizenzfreigabe behauptet. |
| FreeRTOS-eZ80f91 | [Projekt](https://github.com/notwendig/FreeRTOS-eZ80f91), Port-Quellköpfe und Lizenzen der eingebundenen Bibliotheken |
| FreeRTOS-Kernel / Plus-TCP / uzlib | Jeweilige Upstream-Lizenzdateien; Versionen und Kompatibilitätspatches im [FreeRTOS-Buildablauf](https://github.com/notwendig/FreeRTOS-eZ80f91/blob/master/BUILD.md) |
| ZDS II, Nexus SDK und ZTP | Separat installierte Herstellerpakete mit deren Bedingungen; keine SDK-Kopie im Workspace |

Die [Quellenübersicht](sources.md) nennt zusätzlich technische Referenzen.
Die lokalen Hersteller-PDFs können außerhalb des Repositories liegen; ihre
Verfügbarkeit wird beim Klonen nicht vorausgesetzt. Copyright-Hinweise in
übernommenen Quelltexten und die ursprünglichen CamelForth-Hinweise bleiben
bei der Dokumentationsbereinigung erhalten.

`examples/` enthält bewusst gespeicherte, aus den jeweiligen Quellen erzeugte
Testfixtures. Deren Metadaten dokumentieren Herkunft und Hashes. Umfangreiche
SDK-Anwendungen werden stattdessen aus der lokalen Herstellerinstallation in
`build/` erzeugt und dort nicht versioniert.
