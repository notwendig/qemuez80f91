#!/usr/bin/env python3
"""Copy existing CP/M image files to DRIVE/[USER/]filename Unix directories."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--images', type=Path, default=ROOT / 'ez80f91_disks.4040')
    p.add_argument('--out', type=Path, default=ROOT / 'cpm-files')
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = []
    with tempfile.TemporaryDirectory(prefix='cpm-unix-import-') as temp:
        for letter in 'ABCDEFGHIJKLMNOP':
            image = args.images.resolve() / (letter + '.img')
            if not image.is_file():
                continue
            size = image.stat().st_size
            fmt = '4mb-hd' if size == 4194304 else 'ibm-3740' if letter == 'A' else 'ibm-3740-data'
            assert size in (256256, 4194304), image
            count = 0
            for user in range(16):
                extracted = Path(temp) / f'{letter}-{user}'
                extracted.mkdir()
                result = subprocess.run(['cpmcp', '-T', 'logical', '-f', fmt, str(image), f'{user}:*', str(extracted)],
                                        cwd=ROOT / 'images/cpm', capture_output=True, text=True)
                assert result.returncode == 0, result.stderr
                target = args.out / letter
                if user:
                    target /= str(user)
                for source in extracted.iterdir():
                    target.mkdir(parents=True, exist_ok=True)
                    name = target / source.name.lower()
                    data = source.read_bytes()
                    if name.exists():
                        assert name.read_bytes() == data, f'Existing file differs: {name}'
                    else:
                        name.write_bytes(data)
                    manifest.append({'file': str(name.relative_to(args.out)),
                                     'sha256': hashlib.sha256(data).hexdigest()})
                    count += 1
            (args.out / letter).mkdir(exist_ok=True)
            print(f'{letter}: {count} files copied; image unchanged')
    (args.out / '.image-import.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
