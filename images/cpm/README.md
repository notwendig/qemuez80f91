# Raw CP/M disks for CS3

Build system tracks with `python3 tools/cpm/build_system.py`, then regenerate
with `python3 tools/cpm/build_disks.py` from the repository root.
The source directory can be changed with `--source`.

`cs3-abcdij.img` contains six uncompressed disks consecutively, without
padding, headers or CRC trailers:

| Drive | Byte offset | Size | Source |
| --- | ---: | ---: | --- |
| A: | 0 | 256256 | Firmware disk contents with rebuilt raw system tracks |
| B: | 256256 | 256256 | Source directory B, user 0 |
| C: | 512512 | 256256 | Overflow from I, original users preserved |
| D: | 768768 | 256256 | Overflow from C, original users preserved |
| I: | 1025024 | 4194304 | Source directory I, numeric subdirectories as users |
| J: | 5219328 | 4194304 | Source directory J, numeric subdirectories as users |

Total: 9413632 bytes (larger than an 8-MiB window).
Individual images, cpmtools `diskdefs` and SHA256 values
in `layout.json` accompany the combined image. B and I are populated using
`cpmcp`; every imported file is extracted again and compared with its source.
A/B use IBM 3740 geometry, with two boot tracks only on A; B has none.
I/J use `4mb-hd`: 1024 tracks, 32 sectors per track, 2048-byte blocks,
256 directory entries, no boot tracks, `os p2dos`.
Import order is user 0 first, then numeric users, alphabetically within each
user. I's directory overflow is passed to C, then D. Files that do not fit on
C/D are skipped while smaller following files are still attempted. All failed
or unreadable imports are rolled back. `layout.json` records overflow per disk;
`remaining-files.json` lists the 21 files still omitted after D. J's 33 files
fit completely.

## WD2797A device

The current firmware uses the separate raw images through a WD2797A controller:

```sh
qemuez80f91 --kit --run --wd2797a 0x1000 --dev '/path/to/disks'
```

The controller transfers sectors entirely through I/O ports; CS3 disk RAM and
memory banking are no longer used. `A.img`, `B.img`, etc., or plain A/B names
are accepted. Existing images retain their exact raw sizes and contents.
See [register map, geometry extensions and tests](../../docs/wd2797a.md).

Without `--dev`, the starter uses `ez80f91_disks.<debugport>`, retaining existing
files and migrating the previous combined `ez80f91_cs3.<debugport>` on first use.
An explicit directory is used directly. The older combined images remain
artifacts for inspection and migration, rather than current guest memory maps.
