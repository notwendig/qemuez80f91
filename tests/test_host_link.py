#!/usr/bin/env python3
"""Translate physical bridge link settings into the F91's 10/100 PHY modes."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.demo_network import host_link_options

with tempfile.TemporaryDirectory(prefix='f91-host-link-') as temp:
    root = Path(temp)
    members = root / 'br0/brif'
    members.mkdir(parents=True)

    def link(name, speed, duplex, carrier=1, physical=True):
        (members / name).mkdir(exist_ok=True)
        interface = root / name
        interface.mkdir(exist_ok=True)
        if physical:
            (interface / 'device').mkdir(exist_ok=True)
        for field, value in (('speed', speed), ('duplex', duplex), ('carrier', carrier)):
            (interface / field).write_text(str(value) + '\n')

    def check(speed, full):
        assert host_link_options('br0', root) == [
            '-global', f'ez80f91-emac.link-speed={speed}',
            '-global', f'ez80f91-emac.full-duplex={"on" if full else "off"}']

    check(100, True)  # No physical Ethernet information: explicit fallback.
    link('eth0', 1000, 'full')
    link('tap0', 10, 'half', physical=False)
    link('eth-down', 10, 'half', carrier=0)
    check(100, True)  # Gigabit is capped; virtual/down interfaces are ignored.
    link('eth1', 100, 'full')
    check(100, True)
    link('eth1', 10, 'full')
    check(10, True)
    link('eth1', 10, 'half')
    check(10, False)
    link('eth1', 100, 'half')
    check(100, False)
    link('eth1', -1, 'unknown')
    check(100, True)
    link('eth1', 'invalid', 'full')
    check(100, True)
    (root / 'eth1/speed').unlink()
    check(100, True)
print('PASS: host speed/duplex, bridge members, PHY cap, TAP/down filtering and unavailable sysfs values')
