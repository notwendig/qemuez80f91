# CP/M 2.2 drives and native I/O ports

QEMU implements the CP/M file operations. The BIOS and Forth access the device
with real I/O instructions. There is one CP/M 2.2 BIOS and one Kit tab. Each
drive is backed by either an image file or a directory:

```text
cpm-files/
  A/
    pip.com          # A:, user 0
    1/
      sdir.com       # A:, user 1
  B.img              # B: IBM-3740 data image
  I.img              # I: 4-MiB hard-disk image
  D/
    f24all.f24       # D:, user 0
```

Drives are A through P; user directories are 1 through 15. User 0 files are
directly in the drive directory. CP/M names use case-insensitive 8.3 matching.
New files use lowercase Unix names. Hidden files, unrepresentable names and
symlinks are not exposed as CP/M files. Do not create case-duplicate names.

The **CAMEL24** and **CP/M 2.2** Kit tabs share this tree. Files saved in Forth
are immediately visible to CP/M; host edits are visible on the next file open
or directory scan. `--fs-root /path/to/files` selects the shared drive root.
A bare file `B` is also accepted instead of `B.img`. Specifying both `B` and
`B.img` is an error: a drive has exactly one backend. Symlink mounts are ignored.

Image formats are IBM-3740 (256256 bytes, two reserved tracks on A:, no reserved
tracks on other drives, skew 6) and 4mb-hd (4194304 bytes, 2-KiB blocks).
Images are edited in place and preserve geometry, boot tracks and unrelated
files. PIP can copy between image and directory drives in either direction.
Forth LOAD/SAVE uses the same mounts. CP/M image files retain 128-byte record
padding; Forth LOAD stops at Ctrl-Z.

```forth
3 S" F24ALL.F24" LOAD
3 S" WORK.F24" SAVE
1 FS-USER !                 ( select CP/M user 1 for Forth file operations )
```

In **CP/M 2.2**:

```text
a>DIR
a>USER 1
a>SDIR
a>USER 0
a>PIP B:COPY.COM=A:PIP.COM
```

## Eight-bit ports

| Low port byte | Read | Write |
| --- | --- | --- |
| `18h` | WD2797A status | WD command |
| `19h` | Track low | Track low |
| `1Ah` | Sector | Sector |
| `1Bh` | Disk data | Disk data / seek destination |
| `1Ch` | Drive/control | Drive/control |
| `1Dh` | DRQ/INTRQ/READY | Reserved |
| `1Eh` | Track high | Track high |
| `1Fh` | `97h` identifier | Reserved |
| `8Ch` | Console bit 0 RX ready, bit 1 TX ready; bit 7 filesystem present | Reserved |
| `8Dh` | Console byte | Console byte |
| `8Eh` | File-command status: 0 success, FFh error | File command |
| `8Fh` | Response byte stream | Request byte stream |

The devices decode only the low address byte, with mirrors in all 256 upper
address banks. The CPU retains normal Z80 address semantics: `OUT (C),A` and
`IN A,(C)` address **BC**. `OUT (n),A` and `IN A,(n)` use A as the upper port
address byte. The BIOS and Forth console use the immediate-port forms.

Select the mirrored FDC with `--wd2797a 0x18`. In this mode the legacy board
discovery descriptors move to FE40h (WD97) and FE48h (HOST), avoiding the FDC
mirrors. The legacy 16-bit FDC bases remain supported explicitly. FDC sector
access and file services share the same image files. FDC writes persist each
completed sector/track immediately; reads refresh from the file. Directory
drives provide FCB operations, without exposing fabricated raw sectors.

## Filesystem command ABI

Writing command 0 to `8Eh` clears the request. Write request bytes to `8Fh`,
then the command to `8Eh`. Execution is synchronous. Check `8Eh`, then consume
the response from `8Fh`.

| Command | Request | Result |
| --- | --- | --- |
| 1 | BDOS function, DE low/high, memory bank, scratch low/high | HL low/high |
| 2 | Drive number 0..15, user number, 8.3 filename bytes | Open Forth source |
| 3 | None | Source line: length byte, then bytes; zero length means EOF |
| 5 | None | Close source |
| 6 | Drive number 0..15, user number, filename bytes | Save console source history |
| 7 | None | Clear and enable Forth source recording |
| 9 | Bank, CCP address low/high, size low/high | Snapshot CCP for warm boot |
| 10 | None | Restore CCP |
| 11 | Drive number 0..15 | Check BIOS drive presence without changing BDOS default drive |

BDOS disk/file functions 13–40 enter the `HOSTDISPATCH`/`HOSTBDOS` BIOS veneer.
Console functions use the original CP/M BDOS and direct-port BIOS. FCB, DMA,
sequential/random records, current drive/user, login/read-only vectors, search,
create, rename, delete, size and Unix read-only permissions are implemented.
The file limit is 16 MiB. BDOS records are 128 bytes; short reads are padded
with Ctrl-Z. Forth source reads/writes retain text byte lengths and normalize
line endings. Image drives expose their actual DPB, allocation blocks and
read-only/system/archive attributes. Directory-drive allocation queries use
a synthetic 4-MiB DPB; system/archive attributes are not persisted for Unix files.

`CPM/CPM22/HWC.INC` defines all BIOS ports. `BIOS.ASM` contains the direct
IN/OUT implementation and file-service veneer. `HOSTBIOS.INC`, `exbios.c` and
`exbios.h` are removed; no trap opcodes or firmware network disk task are used.

## Build and test

```sh
python3 examples/cpm_hostfs/build.py
python3 examples/camelf91/build.py --hostfs --zds "$ZDS_HOME" --out build/camelf91-hostfs
python3 tests/test_cpm_hostfs.py build/ez80/qemu-system-ez80
python3 tests/test_cpm_hostfs_cli.py build/ez80/qemu-system-ez80
python3 tests/test_wd2797a.py build/ez80/qemu-system-ez80 --8bit
ctest --test-dir build/platform-tools --output-on-failure
```

To copy files from existing images into a fresh Unix tree, preserving the images:

```sh
python3 tools/cpm/import_images.py --images ez80f91_disks.4040 --out cpm-files
```

The importer refuses to replace differing Unix files. Import is optional;
mount existing image files directly when directory access is not wanted.
The CP/M build uses the shared BIOS.ASM and HWC.INC without a HOSTFS variant.

The cpmtools tests and importer explicitly select `-T logical`: libdsk's raw
geometry autodetection can otherwise select a different side order for an
already populated flat image. Keep this option when inspecting these images.
