#!/usr/bin/env python3
"""Trace the original ZTP demo on the real nadibox network; no DHCP simulator."""
import argparse
import fcntl
import json
from pathlib import Path
import select
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--qemu', default='/tmp/qemuez80f91-build-baseline/qemu-system-ez80')
p.add_argument('--out', type=Path, default=ROOT/'build/ztp-tcpudp')
p.add_argument('--tcp-test', action='store_true')
p.add_argument('--udp-test', action='store_true')
p.add_argument('--expect-dhcp', action='store_true')
p.add_argument('--dhcp', action='store_true', help='Compatibility flag: DHCP is always supplied by nadibox')
p.add_argument('--bridge', default='br0')
p.add_argument('--dhcp-server', default='192.168.77.1')
p.add_argument('--bridge-helper', default='/usr/libexec/qemu-bridge-helper')
p.add_argument('--icount', type=int, default=5)
p.add_argument('--seconds', type=float, default=30)
p.add_argument('--trace-steps', type=int, default=0)
p.add_argument('--break-at', type=lambda x: int(x, 0), action='append', default=[])
for cs in range(4):
    p.add_argument(f'--cs{cs}', choices=('ram', 'flash', 'none'))
a = p.parse_args()
out = a.out.resolve()
sys.argv[1:] = [a.qemu]
sys.path.insert(0, str(ROOT/'tests'))
sys.path.insert(0, str(ROOT))
from ez80_testlib import VM
from tools.zds.rsp import RSP
from tools.demo_network import DemoNetworkTest, dhcp_leases, wait_for_bridge

lock = (out/'start.lock').open('w')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    p.error('Dieses Demo läuft bereits; vorhandenen Starter zuerst beenden.')
ports = Path('/sys/class/net')/a.bridge/'brif'
if not ports.is_dir():
    p.error(f'Netzwerkbridge nicht gefunden: {a.bridge}')
previous_ports = {port.name for port in ports.iterdir()}
uart, uart_guest = socket.socketpair()
uart.setblocking(False)
(out/'uart.log').write_bytes(b'')
gdb = out/'probe-gdb.sock'
gdb.unlink(missing_ok=True)
machine = 'ez80f91-freertos,ram-boot=on,osc-frequency=5000000'
machine += ''.join(f',cs{cs}={getattr(a, f"cs{cs}")}' for cs in range(4) if getattr(a, f'cs{cs}'))
vm = VM(out/'tcpudp.bin', serial='chardev:console',
        machine=machine, loader='-kernel',
        extra=('-chardev', f'socket,id=console,fd={uart_guest.fileno()}',
               '-icount', f'shift={a.icount},sleep=off',
               '-nic', f'bridge,id=wire,br={a.bridge},helper={a.bridge_helper}',
               '-object', f'filter-dump,id=capture,netdev=wire,file={out/"network.pcap"}',
               '-global', 'ez80f91-emac.phy-addr=31',
               '-gdb', f'unix:{gdb},server=on,wait=off',
               '-d', 'unimp,guest_errors', '-D', str(out/'qemu.log')),
        pass_fds=(uart_guest.fileno(),))
uart_guest.close()
console = bytearray()
samples = []
network_test = DemoNetworkTest(a.dhcp_server, tcp=a.tcp_test) if a.tcp_test or a.udp_test else None
rsp = RSP.__new__(RSP)
rsp.running = False
rsp.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
rsp.socket.settimeout(5)


def read_console():
    if uart in select.select([uart], [], [], .02)[0]:
        chunk = uart.recv(65536)
        console.extend(chunk)
        with (out/'uart.log').open('ab') as log:
            log.write(chunk)


try:
    wait_for_bridge(vm.p, a.bridge, previous_ports)
    rsp.socket.connect(str(gdb))
    rsp.command('?')
    if a.break_at:
        rsp.step()
        for at in a.break_at:
            rsp.command(f'Z0,{at:x},1')
    rsp.run()
    deadline = time.monotonic()+a.seconds
    next_sample = time.monotonic()+1
    while time.monotonic() < deadline:
        read_console()
        leases = dhcp_leases(out/'network.pcap')
        for lease in leases:
            if lease['mac'] == '00:90:23:00:01:01' and lease['server'] != a.dhcp_server:
                raise RuntimeError(f'Falscher DHCP-Server: {lease["server"]}')
        if network_test:
            network_test.advance(bytes(console), leases, uart)
            if network_test.done:
                break
        rsp.poll()
        if not rsp.running:
            state = rsp.registers()
            samples.append({'break': state})
            print('BREAK', state, flush=True)
            (out/'data-at-break.bin').write_bytes(rsp.memory(0xb80100, 0xb58))
            (out/'ram-at-break.bin').write_bytes(rsp.memory(0xb80000, 0x2000))
            trace = []
            for step in range(a.trace_steps):
                state = rsp.registers()
                trace.append(state)
                if state[0] < 0x40 or not 0xb80000 <= state[9] <= 0xc00000:
                    break
                rsp.step()
            (out/'trace.json').write_text(json.dumps(trace, indent=2))
            for row in trace[-20:]:
                print('TRACE', *[hex(row[i]) for i in [0, 1, 2, 3, 4, 5, 9]], flush=True)
            break
        if time.monotonic() >= next_sample:
            rsp.stop()
            regs = vm.hmp('info registers')
            samples.append({'registers': regs, 'mac': rsp.memory(0x1000020, 0x3a).hex()})
            print(regs.split('PC=')[1].splitlines()[0], flush=True)
            rsp.run()
            next_sample = time.monotonic()+1
    rsp.stop()
    read_console()
    leases = dhcp_leases(out/'network.pcap')
    report = {'bridge': a.bridge, 'expected_dhcp_server': a.dhcp_server,
              'leases': leases, 'samples': samples}
    if network_test:
        report.update(network_test.report())
    (out/'probe.json').write_text(json.dumps(report, indent=2)+'\n')
    print('UART:', console.decode(errors='replace'))
    if a.expect_dhcp:
        assert b'DHCP OK' in console and any(
            l['server'] == a.dhcp_server and l['mac'] == '00:90:23:00:01:01' for l in leases
        ), 'DHCP von nadibox nicht bestätigt'
    if network_test:
        assert network_test.done, network_test.error or 'UDP/TCP-Test nicht abgeschlossen'
finally:
    try:
        vm.close()
    except AssertionError:
        vm.p.wait(timeout=5)
        if vm.p.returncode:
            raise
    finally:
        rsp.socket.close()
        uart.close()
        lock.close()
