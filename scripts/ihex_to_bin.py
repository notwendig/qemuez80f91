#!/usr/bin/env python3
"""Validate Intel HEX and emit a zero-based raw image, filling gaps with FF."""
import argparse
from pathlib import Path

def convert(source, output, limit=0x80000):
    data={};base=0;eof=False
    for line_no,line in enumerate(Path(source).read_text(encoding='ascii').splitlines(),1):
        line=line.strip()
        if not line:continue
        if eof:raise ValueError(f'line {line_no}: data after EOF')
        if not line.startswith(':'):raise ValueError(f'line {line_no}: missing colon')
        record=bytes.fromhex(line[1:])
        if len(record)<5 or len(record)!=record[0]+5 or sum(record)&255:
            raise ValueError(f'line {line_no}: length/checksum error')
        n,offset,kind=record[0],int.from_bytes(record[1:3],'big'),record[3]
        payload=record[4:-1]
        if kind==0:
            for i,value in enumerate(payload):
                addr=base+offset+i
                if not 0<=addr<limit:raise ValueError(f'address outside image: {addr:x}')
                if addr in data and data[addr]!=value:raise ValueError('conflicting overlap')
                data[addr]=value
        elif kind==1:
            if n or offset:raise ValueError('invalid EOF')
            eof=True
        elif kind in (2,4):
            if n!=2 or offset:raise ValueError('invalid base record')
            base=int.from_bytes(payload,'big') << (4 if kind==2 else 16)
        elif kind in (3,5):
            if n!=4 or offset:raise ValueError('invalid entry record')
        else:raise ValueError(f'unsupported record type: {kind}')
    if not eof or not data:raise ValueError('empty image or missing EOF')
    image=bytearray(b'\xff'*(max(data)+1))
    for addr,value in data.items():image[addr]=value
    Path(output).write_bytes(image)
    return len(image)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source');p.add_argument('output')
    args=p.parse_args()
    print(f'{args.output}: {convert(args.source,args.output)} bytes')
