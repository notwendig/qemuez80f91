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
fit completely. The BIOS and CP/M support now use these geometries and directly access the
CS3 image at 200000–AFFFFF, without decompression. Pass
`-M ez80f91-minimal,cs3-file=/absolute/path/to/cs3-abcdij.img` to QEMU.
This attaches writable RAM and preserves the exact raw file length on exit;
there is no flash CRC trailer. `start.sh` creates and uses a per-debug-port
copy named `ez80f91_cs3.<port>` so the bundled template remains reusable.

The previous `cs3-abi.img` (A/B/I) and `cs3-abcdi.img` (A/B/C/D/I) combinations
are also regenerated; their offsets differ from the six-disk layout above.
