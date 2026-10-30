# Getting started

## Requirements

The emulator requires Linux, Git, a C compiler, Python 3, Ninja, pkg-config and
the development libraries requested by QEMU configure, particularly GLib.
QEMU prepares Meson and its Python build environment during configuration.
See [QEMU base](qemu-base.md) for the pinned source revision.

Most ROM tests need only Python and QEMU. Some decoder/decompression tests
also compile host programs with `cc`. Run scripts directly; they are not a pytest suite.

Vendor firmware and debugger integration additionally require:

- **ZDS II eZ80Acclaim! 5.3.5**, including ZTP 2.5.1;
- Wine with access to that installation;
- Nexus SDK 1.1 and `i686-w64-mingw32-gcc` for original-DLL tests;
- Tkinter for the kit window, and `gnome-terminal` or `xterm` for `start.sh`.

Obtain SDKs from their vendors. They are not included in this repository.

## Checkout and QEMU build

```sh
git clone https://github.com/notwendig/qemuez80f91.git
cd qemuez80f91
python3 scripts/setup-dependencies.py
git clone --depth 1 --branch v11.1.2 https://gitlab.com/qemu-project/qemu.git qemu
sh scripts/apply-qemu-patches.sh
mkdir -p build/ez80
cd build/ez80
../../qemu/configure --target-list=ez80-softmmu --disable-docs --disable-werror --without-default-features --enable-tcg --enable-system --disable-tools
ninja -j8 qemu-system-ez80
cd ../..
export QEMU_EZ80="$PWD/build/ez80/qemu-system-ez80"
```

`scripts/setup-dependencies.py` prepares both firmware projects, including the
nested CAMEL BSP and patched FreeRTOS, TCP/IP and uzlib sources. It can be run
again after cloning. A plain clone or outer-submodule initialization leaves
these nested library directories empty; ZDS then reports missing `FreeRTOS.h`
and `No rule to make target` for library sources. Run setup before opening or
rebuilding the ZDS project. `git submodule update --init --recursive` alone
fetches upstream sources but does not apply the required compatibility patches.

`apply-qemu-patches.sh` checks the upstream base and accepts an identical patch
that is already applied. It does not reset an existing development branch.
See [Development](development.md) for maintaining such a checkout.

## Installation and first test

```sh
python3 scripts/install.py
export PATH="$PWD/install/bin:$PATH"
qemuez80f91 --help
```

`qemu-system-ez80` is the emulator; `qemuez80f91` opens this checkout's UART
launcher. The launcher preserves the caller's working directory for flash
files and requires the checkout to remain available. Use `--prefix "$HOME/.local"`
to install into the user profile. `QEMU_EZ80` overrides automatic selection;
otherwise `start.sh` tries `install/bin/`, then `build/ez80/`, then the
historical `/tmp/qemuez80f91-build-baseline/qemu-system-ez80` fallback.

```sh
python3 tests/test_smoke.py "$QEMU_EZ80"
python3 tests/test_cpu_uart.py "$QEMU_EZ80"
"$QEMU_EZ80" -M ez80f91-minimal -bios examples/hello_uart0.bin \
  -display none -monitor none -serial mon:stdio -nic none
```

Expected output: `Hello eZ80F91`, followed by guest HALT. QEMU remains open;
**Ctrl+A, X** exits. Tests require local sockets.

## ZDS and firmware

```sh
export ZDS_HOME="$HOME/.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5"
sh scripts/setup-camelf91.sh
python3 examples/camelf91/build.py --zds "$ZDS_HOME"
python3 tools/zds/f24.py --prepare-only
```

The CAMEL polling build reads corrected sources directly from pinned commit
`af47e6520adc220cef5ee7e9ab96f0c336f7e299`; no separate CAMEL patches are applied.
It enables the shared kit includes and uses its own polling UART startup.
For the native project, build `libbsp/libbsp.zdsproj` first, then
`camel_f91.zdsproj`. See [CamelForth](camelf91.md).

FreeRTOS has a separate [dependency and build procedure](../subprojects/FreeRTOS-eZ80f91/BUILD.md).
The pinned versions are kernel V11.3.2, TCP/IP V4.4.2 and uzlib `6d60d65`.
The [ZTP demonstration](ztp-tcpudp.md) builds a separate copy of the locally
installed vendor example.

## UART, networking and kit

`./start.sh --kit` opens UART and kit windows with the CPU waiting for ZDS.
`--run` starts the saved flash immediately. **Ctrl+C** in the UART terminal
stops the instance and saves its flash.

The launcher requires an existing `br0` and a configured QEMU bridge helper.
It changes neither the host bridge nor DHCP settings. On the development
network, nadibox at `192.168.77.1` supplies leases. The [demo tools](ztp-tcpudp.md)
accept explicit bridge/server settings for other environments.

Debugger TCP 4040 and discovery UDP 3000 are independent of guest Ethernet.
A second instance must use another debug port, for example `./start.sh dbgport 4041`.

## Using another network

`nadibox` is the development LAN's DHCP server, not a requirement of the
FreeRTOS firmware. Any suitable external DHCP server or router can supply a
lease. Connect the host bridge to the desired LAN; the launchers do not create
the bridge or configure a DHCP server.

The `start.sh` launcher currently fixes the bridge and helper in
[`tools/start.py`](../tools/start.py). To use another bridge, update the
`/sys/class/net/br0/brif` check, `br=br0` backend option and `start_after_bridge`
argument together, plus the diagnostic message. Update the helper path if your
system installs it elsewhere. Permit the selected bridge in the helper's
allowlist, normally `/etc/qemu/bridge.conf` (for example, `allow br1`).

The separate ZTP launcher accepts `--bridge`, `--bridge-helper` and
`--dhcp-server` instead. Its `--dhcp-server` value identifies the expected server
for lease validation; it does not start or reconfigure that server.

Application clients use the guest's assigned DHCP address. ZDS Ethernet Smart
Cable uses the host address, or `127.0.0.1` when ZDS runs on the same host.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing `FreeRTOS.h` / library source targets | Run `python3 scripts/setup-dependencies.py`, then **Rebuild All** in ZDS. |
| QEMU executable not found | Set `QEMU_EZ80` to the executable you built. |
| No UART banner | Resume with F5 in ZDS; load the matching RAM/flash target. |
| CAMEL DTL write failure at 100000h | Disable external flash autodetection in the RAM debug target. |
| Dark kit display | Use `--kit`, enable CS2 over 800000h and run display firmware. |
| No DHCP | Check TAP forwarding, bridge, DHCP server and guest PHY address. |
| Old behavior after rebuilding | Restart QEMU/kit and reload firmware; running processes do not reload files. |
| IPv4 logs start with 255 instead of 192 | Rebuild and reload the updated TCP/IP compatibility sources; see [Build](../subprojects/FreeRTOS-eZ80f91/BUILD.md). |

Flash files contain saved guest data. Do not delete them as if they were caches.
