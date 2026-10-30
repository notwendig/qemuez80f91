#!/usr/bin/env python3
"""Build raw A/B/C/D/I/J disks, using C/D for I's overflow."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('/home/juergen/Projects/zilogz80-code/CPM22/disks'))
    parser.add_argument('--output', type=Path, default=ROOT / 'images/cpm')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    fixture = (ROOT / 'subprojects/FreeRTOS-eZ80f91/CPM/CPM22_A.c').read_text()
    body = fixture[fixture.index('{') + 1:fixture.index('}')]
    a = gzip.decompress(bytes(int(x, 16) for x in re.findall(r'0x([0-9a-fA-F]{2})', body)))
    assert len(a) == 77 * 26 * 128
    system = args.output / 'system.bin'
    if not system.exists():
        raise FileNotFoundError('Build updated system tracks first: python3 tools/cpm/build_system.py')
    boot = system.read_bytes()
    assert 0 < len(boot) <= 2 * 26 * 128
    a = boot + a[len(boot):]
    definitions = '''diskdef ibm-3740
  seclen 128
  tracks 77
  sectrk 26
  blocksize 1024
  maxdir 64
  skew 6
  boottrk 2
  os 2.2
end
diskdef ibm-3740-data
  seclen 128
  tracks 77
  sectrk 26
  blocksize 1024
  maxdir 64
  skew 6
  boottrk 0
  os 2.2
end
diskdef 4mb-hd
  seclen 128
  tracks 1024
  sectrk 32
  blocksize 2048
  maxdir 256
  skew 1
  boottrk 0
  os p2dos
end
'''
    layout = []
    combined = bytearray()
    images = {}
    overflow = []
    remaining = []
    with tempfile.TemporaryDirectory(prefix='cpm-images-') as work:
        work = Path(work)
        (work / 'diskdefs').write_text(definitions)
        for drive, fmt, size in [('A', 'ibm-3740', len(a)), ('B', 'ibm-3740-data', len(a)), ('I', '4mb-hd', 4 * 1024 * 1024), ('C', 'ibm-3740-data', len(a)), ('D', 'ibm-3740-data', len(a)), ('J', '4mb-hd', 4 * 1024 * 1024)]:
            image = work / (drive + '.img')
            files = []
            skipped = []
            if drive == 'A':
                image.write_bytes(a)
            else:
                image.write_bytes(bytes(size))
                subprocess.run(['mkfs.cpm', '-f', fmt, str(image)], cwd=work, check=True)
                source = args.source / drive
                if drive in ('C', 'D'):
                    files = [(entry['user'], Path(entry['file'])) for entry in overflow]
                for item in sorted(source.iterdir()) if drive not in ('C', 'D') else []:
                    if item.is_file():
                        files.append((0, item))
                    elif item.is_dir() and item.name.isdecimal() and 0 <= int(item.name) <= 15:
                        files.extend((int(item.name), f) for f in sorted(item.iterdir()) if f.is_file())
                    else:
                        raise ValueError(f'Unsupported source entry: {item}')
                imported = []
                files.sort(key=lambda entry: (entry[0], entry[1].name))
                for index, (user, f) in enumerate(files):
                    before = image.read_bytes()
                    result = subprocess.run(['cpmcp', '-f', fmt, str(image), str(f.resolve()), f'{user}:'], cwd=work, capture_output=True, text=True)
                    if not result.returncode:
                        probe = work / 'probe'
                        probe.unlink(missing_ok=True)
                        readback = subprocess.run(['cpmcp', '-f', fmt, str(image), f'{user}:{f.name}', str(probe)], cwd=work, capture_output=True, text=True)
                        if readback.returncode:
                            if drive not in ('C', 'D'):
                                raise RuntimeError(readback.stderr)
                            image.write_bytes(before)
                            skipped.append(dict(user=user, file=str(f)))
                            continue
                        original = f.read_bytes()
                        actual = probe.read_bytes()
                        assert actual[:len(original)] == original, f
                    if result.returncode:
                        if not any(reason in result.stderr.lower() for reason in ('directory full', 'disk full', 'device full')):
                            raise RuntimeError(result.stderr)
                        image.write_bytes(before)
                        if drive in ('C', 'D'):
                            skipped.append(dict(user=user, file=str(f)))
                            continue
                        skipped = [dict(user=u, file=str(p)) for u, p in files[index:]]
                        break
                    imported.append((user, f))
                files = imported
                if drive in ('I', 'C', 'D'):
                    overflow = skipped
                if drive in ('D', 'J'):
                    remaining.extend(dict(drive=drive, **entry) for entry in skipped)
                # Verify every imported file, including CP/M record padding.
                for index, (user, f) in enumerate(files):
                    extracted = work / f'verify-{index}'
                    subprocess.run(['cpmcp', '-f', fmt, str(image), f'{user}:{f.name}', str(extracted)], cwd=work, check=True)
                    original = f.read_bytes()
                    actual = extracted.read_bytes()
                    assert actual[:len(original)] == original, f
                    assert len(original) <= len(actual) <= (len(original) + 127) // 128 * 128, f
            subprocess.run(['cpmls', '-f', fmt, str(image)], cwd=work, check=True, stdout=subprocess.DEVNULL)
            data = image.read_bytes()
            assert len(data) == size
            images[image.name] = data
            layout.append(dict(drive=drive, offset=len(combined), size=len(data), format=fmt, imported_files=len(files), skipped_files=skipped, sha256=hashlib.sha256(data).hexdigest()))
            combined.extend(data)
    layout.sort(key=lambda disk: 'ABCDIJ'.index(disk['drive']))
    combined = bytearray()
    for disk in layout:
        disk['offset'] = len(combined)
        combined.extend(images[disk['drive'] + '.img'])
    for name, data in images.items():
        (args.output / name).write_bytes(data)
    (args.output / 'cs3-abi.img').write_bytes(images['A.img'] + images['B.img'] + images['I.img'])
    (args.output / 'cs3-abcdi.img').write_bytes(combined[:-len(images['J.img'])])
    (args.output / 'cs3-abcdij.img').write_bytes(combined)
    (args.output / 'remaining-files.json').write_text(json.dumps(remaining, indent=2) + '\n')
    (args.output / 'diskdefs').write_text(definitions)
    (args.output / 'layout.json').write_text(json.dumps(layout, indent=2) + '\n')
    for disk in layout:
        print(f"{disk['drive']}: {disk['size']} bytes, {disk['imported_files']} imported, {len(disk['skipped_files'])} skipped")


if __name__ == '__main__':
    main()
