#!/usr/bin/env python3
"""Raw CS3 image persistence and all six CP/M drive boundaries."""
from pathlib import Path
import subprocess
import tempfile
from ez80_testlib import VM

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='cpm-cs3-') as temp:
    work = Path(temp)
    # Run the same address arithmetic as the ZDS guest, with overflow-sensitive
    # high tracks and rejected accesses at both ends of every device.
    check = work / 'bounds.c'
    check.write_text('''#include <stddef.h>
#include <assert.h>
#include "cpm_disks.h"
int main(void) {
    size_t offsets[] = {0,256256,512512,768768,1025024,5219328};
    unsigned char drives[] = {0,1,2,3,8,9};
    for(int i=0;i<6;i++) {
        unsigned short tracks=i<4?77:1024, sectors=i<4?26:32;
        size_t at=0, size=i<4?256256:4194304;
        assert(cpm_disk_sector(drives[i],0,1,&at) && at==offsets[i]);
        assert(cpm_disk_sector(drives[i],tracks-1,sectors,&at));
        assert(at==offsets[i]+size-128);
        assert(!cpm_disk_sector(drives[i],tracks,1,&at));
        assert(!cpm_disk_sector(drives[i],0,0,&at));
        assert(!cpm_disk_sector(drives[i],0,sectors+1,&at));
    }
    size_t at; assert(!cpm_disk_sector(4,0,1,&at));
    return 0;
}
''')
    subprocess.run(['cc', '-I', str(ROOT / 'subprojects/FreeRTOS-eZ80f91/CPM'),
                    str(check), '-o', str(work / 'bounds')], check=True)
    subprocess.run([str(work / 'bounds')], check=True)
    image = work / 'disks.img'
    original = bytearray((ROOT / 'images/cpm/cs3-abcdij.img').read_bytes())
    image.write_bytes(original)
    # ADL: disable CS0, map CS3 200000..AFFFFF, read I/J end and write J end.
    rom = bytearray([0x5b,0xc3,5,0,0])
    def out(port,value): rom.extend([0x3e,value,0xed,0x39,port])
    def ld(op,addr): rom.extend([op,*addr.to_bytes(3,'little')])
    out(0xaa,0);out(0xb3,0);out(0xb1,0x20);out(0xb2,0xaf);out(0xb3,8)
    end = 0x200000 + len(original) - 1
    ld(0x3a,end);ld(0x32,0xffe100)
    rom.extend([0x3e,0x42]);ld(0x32,end);rom.append(0x76)
    firmware = work / 'test.bin';firmware.write_bytes(rom)
    for attempt in range(2):
        vm = VM(firmware, machine=f'ez80f91-minimal,cs3-file={image}', extra=('-nic','none'))
        try:
            vm.cmd('cont');vm.halted();vm.cmd('stop')
            sample = work / 'sample'
            vm.cmd('pmemsave',dict(val=0xffe100,size=1,filename=str(sample)))
            assert sample.read_bytes() == bytes([original[-1] if not attempt else 0x42])
        finally:
            vm.close()
        expected = original.copy();expected[-1]=0x42
        assert image.read_bytes()==expected
    print('PASS: six drive boundaries; CS3 >8MiB load/write/save/restart, raw length preserved')
