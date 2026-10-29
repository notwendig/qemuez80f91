#!/usr/bin/env python3
"""Compare the decoder against the documented UM0077 opcode maps (106–112).

This checks legal and reserved bytes in both reset/Z80 and ADL modes. Expected
sets are transcribed from the manual, not computed from decoder masks. Prefix
operand rules and execution semantics are covered by the ROM-level tests.
"""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
DISPATCHERS={0x40,0x49,0x52,0x5b,0xcb,0xdd,0xed,0xfd}

def rows(items):
    return {16*high+int(low,16) for high,item in enumerate(items) for low in item}

ED=rows(['01234789cf','01234789cf','01234789cf','1234789cef',
         '0123456789abcdf','0123456789abcef','0123456789abcdef','234689abcde',
         '234abc','234abc','0123489abc','0123489abc','237ab','7','',''])
INDEX=rows(['79f','79f','12345679abcdef','145679ef','456cde','456cde',
            '0123456789abcdef','0123457cde','456cde','456cde','456cde','456cde',
            '','','1359','9'])
CB=set(range(256))-set(range(0x30,0x38))
INDEX_CB=rows(['6e']*3+['e']+['6e']*12)
EXPECTED=[set(range(256))-DISPATCHERS,ED,INDEX,INDEX,CB,INDEX_CB,INDEX_CB]
NAMES=['base','ED','DD','FD','CB','DD CB d','FD CB d']
C=r'''
#include <stdio.h>
#include <string.h>
#include "decode.h"
static uint8_t code[16];
static uint8_t read_code(void *opaque,uint32_t address)
{
    (void)opaque;
    return code[address&15];
}
int main(void)
{
    for(unsigned adl=0;adl<2;adl++) {
        for(unsigned group=0;group<7;group++) {
            for(unsigned opcode=0;opcode<256;opcode++) {
                memset(code,0,sizeof(code));
                if(group==0) code[0]=opcode;
                else if(group<5) {
                    code[0]=(uint8_t[]){0,0xed,0xdd,0xfd,0xcb}[group];code[1]=opcode;
                } else { code[0]=group==5?0xdd:0xfd;code[1]=0xcb;code[3]=opcode; }
                EZ80Decode instruction={.read=read_code,.adl=adl};ez80_decode(&instruction);
                printf("%u %u %u %u\n",adl,group,opcode,instruction.valid);
            }
        }
    }
}
'''
with tempfile.TemporaryDirectory(prefix='ez80-opcode-map-') as temporary:
    out=Path(temporary)
    cpu=(ROOT/'qemu/target/ez80/cpu.h').read_text()
    constants='\n'.join(line for line in cpu.splitlines() if line.startswith('#define EZ80_'))
    (out/'constants.h').write_text('#include <stdint.h>\n#include <stdbool.h>\n'+constants+'\n')
    decoder=(ROOT/'qemu/target/ez80/decode.h').read_text().replace('#include "cpu.h"','#include "constants.h"')
    (out/'decode.h').write_text(decoder);(out/'test.c').write_text(C)
    subprocess.run(['cc','-std=gnu11','-O2',str(out/'test.c'),'-o',str(out/'test')],check=True)
    data=subprocess.check_output([str(out/'test')],text=True)
    for line in data.splitlines():
        adl,group,opcode,valid=map(int,line.split())
        if group==0 and opcode in DISPATCHERS:continue
        if group in (2,3) and opcode==0xcb:continue
        assert bool(valid)==(opcode in EXPECTED[group]),(NAMES[group],adl,f'{opcode:02x}',valid)
    for name,expected in zip(NAMES,EXPECTED):print(f'PASS: {name}: {len(expected)} documented encodings, both ADL modes')
print('PASS: all seven documented opcode maps; reserved bytes remain invalid')
