# Technische Grundlagen

## Herstellerdokumentation

- [eZ80F91 MCU Product Specification, PS0192](https://www.zilog.com/docs/ez80acclaim/ps0192.pdf)
- [eZ80 CPU User Manual, UM0077](https://www.zilog.com/docs/um0077.pdf)
- [eZ80F91 Modular Development Kit, UM0170](https://www.zilog.com/docs/ez80acclaim/devtools/um0170.pdf)

Bei der Implementierung werden Dokumentrevision und die tatsächlich verwendete
F91-Variante festgehalten. Die lokalen Herstellerdokumente liegen in `../doc/`: `ps0192.pdf`
(PS019217-1222) und `um0077.pdf` (UM007715-0415).
Die geprüfte Abgrenzung und Resetbelegung stehen in
[Implementierungsgrundlage](ez80f91-baseline.md).

## Zu untersuchender Quellcode

- [Offizielles QEMU](https://gitlab.com/qemu-project/qemu)
- [QEMU-Architekturen](https://www.qemu.org/docs/master/about/emulation.html)
- [CEmu](https://github.com/CE-Programming/CEmu): Emulator eZ80-basierter
  TI-Taschenrechner, GPLv3; möglicher CPU-Referenzcode, kein F91-SoC-Modell.
- [WilliamTowle/qemu-z80](https://github.com/WilliamTowle/qemu-z80): separater
  Z80-QEMU-Fork; eZ80F91-Unterstützung ist damit nicht nachgewiesen.

Fremdprojekte werden mit Herkunft, Lizenzhinweisen und genauem Commit
getrennt festgehalten. CAMELF91_24 ist als Git-Submodul eingebunden;
[Einbindung und Testumfang](camelf91.md).

## FreeRTOS-Referenzprojekt

- https://github.com/notwendig/FreeRTOS-eZ80f91
- Geprüfter Commit: `cc64b750e7a5c6dfd19dd8eb3a644a9243ce10a9`.
- RAM-Target, veröffentlichte Linker-Map und unveränderter C-Startup dienen
  als konkrete Referenz. Umfang und Prüfergebnis: [FreeRTOS-C-Startup](freertos-boot.md).

## CAMELF91_24

- https://github.com/notwendig/CAMELF91_24
- Festgelegter Commit: `b975f3acac08c70c05d951aad22e5c1824446206`.
- Submodul: `subprojects/CAMELF91_24`.
- Festgelegter Kern mit separat dokumentierten Korrekturpatches, Original-Startup
  und Polling-Test-BSP; Details und
  Hinweise zur nicht abrufbaren Original-BSP-Abhängigkeit: [CamelForth](camelf91.md).
