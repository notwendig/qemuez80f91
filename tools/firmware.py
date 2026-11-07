#!/usr/bin/env python3
"""Build the FreeRTOS ZDS project and program QEMU flash without the ZDS IDE."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT = ROOT / 'subprojects/FreeRTOS-eZ80f91/EZ80F910300ZCOG.zdsproj'
sys.path.insert(0, str(ROOT / 'scripts'))
from ihex_to_bin import convert


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def win(path):
    return 'Z:' + str(Path(path).resolve()).replace('/', '\\')


def default_zds():
    candidates = [os.environ.get('ZDS_HOME', ''), str(ROOT.parent / 'ZDSII_eZ80Acclaim!_5.3.5'),
                  str(Path.home() / '.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5')]
    return next((Path(p) for p in candidates if p and (Path(p) / 'bin/ez80cc.exe').is_file()), Path(candidates[-1]))


class Project:
    def __init__(self, args):
        self.path = args.project.resolve()
        self.root = self.path.parent
        self.zds = args.zds.resolve()
        self.config = args.config
        self.out = (args.out or ROOT / 'build/firmware' / self.config).resolve()
        tree = ET.parse(self.path).getroot()
        if tree.findtext('cpu', '').lower() != 'ez80f91':
            raise ValueError('This build frontend supports the eZ80F91 project.')
        cfg = tree.find(f"configurations/configuration[@name='{self.config}']")
        if cfg is None:
            raise ValueError(f'Unknown configuration: {self.config}')
        self.opts = {tool.attrib['name']: {o.attrib['name']: o.text or ''
                     for o in tool.findall('options/option')} for tool in cfg.findall('tools/tool')}
        self.sources = [self.resolve(f.text) for f in tree.findall('files/file')
                        if f.text.lower().endswith(('.c', '.asm'))]
        stems = [p.stem.lower() for p in self.sources]
        if len(set(stems)) != len(stems):
            raise ValueError('Source basenames must be unique for Zilog object files.')
        for p in self.sources:
            if not p.is_file():
                raise ValueError(f'Source missing: {p}; run scripts/setup-dependencies.py')
        target = self.opt('Debugger', 'target')
        self.target_path = self.root / (target + '.ztgt')
        self.target = ET.parse(self.target_path).getroot()
        if self.target.findtext('Clock/clockType') != 'oscillator':
            raise ValueError('Only the project oscillator clock profile is supported.')
        self.debug = self.opt('General', 'debug') == 'true'
        self.name = Path(self.opt('Linker', 'of').replace('\\', '/')).name
        self.rom = self.ranges('rom')
        self.ram = self.ranges('ram')

    def opt(self, tool, name, default=''):
        return self.opts.get(tool, {}).get(name, default)

    def resolve(self, path):
        path = re.sub(r'\\+', '/', path)
        match = re.search(r'ZDSII_eZ80Acclaim![^/]*/(.*)', path, re.I)
        if match:
            return (self.zds / match[1]).resolve()
        if re.match(r'^[A-Za-z]:', path):
            raise ValueError(f'Unmapped Windows path in project: {path}')
        return (self.root / path).resolve()

    def ranges(self, name):
        result = []
        for item in self.opt('Linker', name).split(','):
            lo, hi = item.strip().split('-')
            result.append((int(lo, 16), int(hi, 16)))
        return result

    def includes(self, tool, name):
        paths = [self.root] + [self.resolve(x) for x in self.opt(tool, name).split(';') if x]
        paths += [self.zds / 'include/std', self.zds / 'include/zilog']
        return list(dict.fromkeys(paths))

    def asm_flags(self):
        flags = ['-cpu:eZ80F91']
        flags += ['-define:' + d for d in self.opt('Assembler', 'define').split(',') if d]
        flags += ['-include:' + ';'.join(map(win, self.includes('Assembler', 'include')))]
        for name in ('list', 'listmac', 'name', 'quiet', 'sdiopt'):
            flags.append(('-' if self.opt('Assembler', name) == 'true' else '-NO') + name)
        flags += ['-pagelen:0', '-pagewidth:132', '-warn', '-NOigcase']
        flags += ['-debug' if self.debug else '-NOdebug']
        return flags

    def cc_flags(self):
        flags = ['-cpu:eZ80F91', '-nolink']
        flags += ['-define:' + d for d in self.opt('Compiler', 'define').split(',') if d]
        for name in ('genprintf', 'keepasm', 'keeplst', 'list', 'listinc', 'modsect',
                     'promote', 'reduceopt', 'multithread'):
            flags.append(('-' if self.opt('Compiler', name) == 'true' else '-NO') + name)
        flags += ['-optspeed' if self.opt('Compiler', 'optspeed') == 'true' else '-optsize',
                  '-debug' if self.debug else '-NOdebug', '-NOpadbranch']
        flags += ['-stdinc:' + ';'.join(map(win, self.includes('Compiler', 'stdinc'))),
                  '-usrinc:' + ';'.join(map(win, self.includes('Compiler', 'usrinc')))]
        asm = self.asm_flags()
        # These quotes belong to the compiler's child assembler command line.
        asm = [f'-include:"{x[len("-include:"):]}"' if x.startswith('-include:') else x for x in asm]
        flags += ['-asmsw:' + ' '.join(asm)]
        return flags

    def link_text(self):
        lines = ['-FORMAT=OMF695,INTEL32', '-map -maxhexlen=64 -quiet -warnoverlap -xref -unresolved=fatal',
                 '-sort ' + self.opt('Linker', 'sort', 'NAME') + '=ascending -warn -NOigcase ' +
                 ('-debug' if self.debug else '-NOdebug')]
        for name in ('rom', 'ram', 'extio', 'intio'):
            ranges = self.opt('Linker', name)
            lines.append('RANGE ' + name.upper() + ' ' + ', '.join(
                '$' + x.strip().replace('-', ' : $') for x in ranges.split(',')))
        lines += ['CHANGE STRSECT is ROM', 'ORDER .RESET,.IVECTS,.STARTUP,CODE,DATA', 'COPY DATA ROM',
                  'DEFINE __low_romdata = copy base of DATA', 'DEFINE __low_data = base of DATA',
                  'DEFINE __len_data = length of DATA', 'DEFINE __low_bss = base of BSS',
                  'DEFINE __len_bss = length of BSS', 'DEFINE __stack = highaddr of RAM + 1',
                  'DEFINE __heaptop = highaddr of RAM', 'DEFINE __heapbot = top of RAM + 1',
                  'DEFINE __low_romcode = copy base of CODE', 'DEFINE __low_code = base of CODE',
                  'DEFINE __len_code = length of CODE', 'DEFINE __copy_code_to_ram = 0', 'DEFINE __crtl = 1']
        for n in range(4):
            cs = self.target.find(f'Memory/ChipSelects/CS{n}')
            for key, field in [('LBR', 'lower'), ('UBR', 'upper'), ('CTL', 'controlRegister'), ('BMC', 'busMode')]:
                lines.append(f'DEFINE __CS{n}_{key}_INIT_PARAM = ${cs.findtext(field)}')
        internal = self.target.find('Memory/Internal')
        ram_ctl = (0x80 if internal.findtext('useInternalDataRam') == 'true' else 0) | (0x40 if internal.findtext('useMaccRam') == 'true' else 0)
        flash_ctl = int(self.target.findtext('Memory/waitStates'), 16) << 5
        flash_ctl |= 8 if internal.findtext('useFlashRam') == 'true' else 0
        for key, value in [('RAM_CTL', f'{ram_ctl:X}'), ('RAM_ADDR_U', internal.findtext('mapRamToPage')),
                           ('FLASH_CTL', f'{flash_ctl:X}'), ('FLASH_ADDR_U', internal.findtext('mapFlashToPage'))]:
            lines.append(f'DEFINE __{key}_INIT_PARAM = ${value}')
        clock = self.target.findtext('Clock/frequency')
        lines += [f'DEFINE _SYS_CLK_FREQ = {clock}', f'DEFINE _OSC_FREQ = {clock}',
                  'DEFINE _SYS_CLK_SRC = 0', 'DEFINE _OSC_FREQ_MULT = 1', 'DEFINE __PLL_CTL0_INIT_PARAM = $40']
        objects = [win(self.out / (p.stem + '.obj')) for p in self.sources]
        suffix = 'D' if self.debug else ''
        objects += [win(self.zds / f'lib/std/{name}{suffix}.lib') for name in ('chelp', 'crt', 'crtM', 'nokernel')]
        objects += [win(self.zds / 'lib/zilog/zsldevinitdummy.obj')]
        lines += [f'"{self.name}" = ' + ', \\\n'.join('"' + x + '"' for x in objects)]
        return '\n'.join(lines) + '\n'


def diagnostic(line, project):
    match = re.match(r'^(.*?)\s*\((\d+)(?:,\s*(\d+))?\)\s*:\s*(ERROR|WARNING)\s*\((\d+)\)\s*(.*)', line, re.I)
    if not match:
        return line
    file, number, column, severity, code, message = match.groups()
    file = file.strip()
    if file.lower().startswith('z:'):
        file = file[2:].replace('\\', '/')
    elif not file.startswith('/'):
        file = str(next((p for p in project.sources if p.name.lower() == Path(file).name.lower()), project.out / file))
    file = next((str(p) for p in project.sources if str(p).lower() == file.lower()), file)
    # Compiler messages lowercase Windows filenames; Linux paths keep their case.
    if not Path(file).exists():
        actual = Path('/')
        for part in Path(file).parts[1:]:
            candidate = actual / part
            if not candidate.exists() and actual.is_dir():
                candidate = next((p for p in actual.iterdir() if p.name.lower() == part.lower()), candidate)
            actual = candidate
        file = str(actual)
    return f'{file}:{max(1, int(number))}:{max(1, int(column or 1))}: {severity.lower()} Z{code}: {message}'


def build(args):
    project = Project(args)
    project.out.mkdir(parents=True, exist_ok=True)
    with (project.out / 'build.lock').open('a+b') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f'Build already running: {project.out}')
        return _build(args)


def _build(args):
    p = Project(args)
    p.out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, WINEPREFIX=str(args.wine_prefix.resolve()), WINEDEBUG='-all')
    def run(exe, flags):
        command = ['wine', str(p.zds / 'bin' / exe), *flags]
        with (p.out / 'build.log').open('a') as log:
            log.write(subprocess.list2cmdline(command) + '\n')
            process = subprocess.Popen(command, cwd=p.out, env=env, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, errors='replace')
            for line in process.stdout:
                log.write(line)
                if line.strip():
                    print(diagnostic(line.rstrip(), p), flush=True)
            if process.wait():
                raise RuntimeError(f'{exe} failed; see {p.out / "build.log"}')
    for name in ('ez80cc.exe', 'ez80asm.exe', 'eZ80link.exe'):
        if not (p.zds / 'bin' / name).is_file():
            raise ValueError(f'Zilog tool missing: {p.zds / "bin" / name}; set ZDS_HOME')
    # All source/header dependencies participate in the cache key, including new/deleted headers.
    headers = sorted({path for base in (p.root, ROOT / 'subprojects/CAMELF91_24/asm')
                      for path in base.rglob('*') if path.suffix.lower() in ('.h', '.inc')})
    shared = hashlib.sha256()
    for path in [p.path, p.target_path, Path(__file__).resolve(), *headers,
                 p.zds / 'bin/ez80cc.exe', p.zds / 'bin/ez80asm.exe']:
        shared.update(str(path).encode()); shared.update(path.read_bytes())
    shared.update(json.dumps([p.asm_flags(), p.cc_flags()]).encode())
    signature = shared.hexdigest()
    state_path = p.out / 'build-state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    state = state if state.get('signature') == signature and not args.rebuild else {}
    cache = state.get('sources', {})
    commands = []
    changed = False
    for n, source in enumerate(p.sources, 1):
        flags = p.cc_flags() if source.suffix.lower() == '.c' else p.asm_flags()
        exe = 'ez80cc.exe' if source.suffix.lower() == '.c' else 'ez80asm.exe'
        commands.append({'directory': str(p.out), 'file': str(source),
                         'arguments': ['wine', str(p.zds / 'bin' / exe), *flags, win(source)]})
        key = digest(source)
        obj = p.out / (source.stem + '.obj')
        if cache.get(str(source)) == key and obj.is_file():
            continue
        print(f'[{n}/{len(p.sources)}] {source.relative_to(p.root) if source.is_relative_to(p.root) else source}', flush=True)
        # A failed/cancelled rebuild must not leave a valid cache for partial objects.
        state_path.unlink(missing_ok=True)
        run(exe, [*flags, win(source)])
        if not obj.is_file():
            actual = next((x for x in p.out.iterdir() if x.name.lower() == obj.name.lower()), None)
            if actual is None:
                raise RuntimeError(f'Compiler did not produce {obj.name}')
            actual.rename(obj)
        cache[str(source)] = key
        changed = True
    (p.out / 'compile_commands.json').write_text(json.dumps(commands, indent=2) + '\n')
    link = p.link_text()
    link_path = p.out / 'firmware.linkcmd'
    relink = changed or not link_path.exists() or link_path.read_text() != link or not (p.out / (p.name + '.hex')).is_file()
    link_path.write_text(link)
    if relink:
        state_path.unlink(missing_ok=True)
        run('eZ80link.exe', ['@firmware.linkcmd'])
    hex_path = p.out / (p.name + '.hex')
    raw = p.out / 'address-space.bin'
    convert(hex_path, raw, 0x1000000)
    data = raw.read_bytes()
    flash = [(0, 0x40000)]
    if p.target.findtext('ExtFlash/usingExternal') == 'true':
        base = int(p.target.findtext('ExtFlash/externalAddress'), 16)
        if p.target.findtext('ExtFlash/device') != 'Am29LV008BB' or p.target.findtext('ExtFlash/units') != '1':
            raise ValueError('Only the configured single AM29LV008BB external flash is supported.')
        flash.append((base, 0x100000))
    images = []
    for base, size in flash:
        filename = 'internal.bin' if base == 0 else 'external.bin'
        payload = data[base:base + size].ljust(size, b'\xff')
        (p.out / filename).write_bytes(payload)
        images.append({'base': base, 'size': size, 'file': filename, 'sha256': digest(p.out / filename)})
    manifest = {'project': str(p.path), 'configuration': p.config, 'target': str(p.target_path),
                'hex': str(hex_path), 'hex_sha256': digest(hex_path), 'images': images}
    (p.out / 'build.json').write_text(json.dumps(manifest, indent=2) + '\n')
    state_path.write_text(json.dumps({'signature': signature, 'sources': cache}, indent=2) + '\n')
    print(f'Build OK: {hex_path}' + (' (up to date)' if not relink else ''), flush=True)
    return p.out / 'build.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build'])
    parser.add_argument('--project', type=Path, default=DEFAULT_PROJECT)
    parser.add_argument('--config', choices=['Debug', 'Release'], default='Release')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--zds', type=Path, default=default_zds())
    parser.add_argument('--wine-prefix', type=Path, default=Path(os.environ.get('WINEPREFIX', '/tmp/qemuez80f91-zds-wine')))
    parser.add_argument('--rebuild', action='store_true')
    args = parser.parse_args()
    try:
        build(args)
    except (ValueError, RuntimeError, OSError, ET.ParseError) as error:
        print(f'firmware: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
