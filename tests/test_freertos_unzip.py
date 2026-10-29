#!/usr/bin/env python3
"""Exercise the actual CP/M gzip wrapper and uzlib with fixture, CRC and size failures."""
import ctypes
import gzip
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]/'subprojects/FreeRTOS-eZ80f91'
with tempfile.TemporaryDirectory(prefix='freertos-unzip-') as td:
    work=Path(td)
    (work/'FreeRTOS.h').write_text('#include <stddef.h>\n#include <stdint.h>\nstruct uzlib_uncomp;\ntypedef int (*progres_t)(struct uzlib_uncomp *);\n')
    (work/'FreeRTOS_IP.h').write_text('')
    src=ROOT/'uzlib/src';library=work/'unzip.so'
    subprocess.run(['cc','-shared','-fPIC','-O1','-I'+str(work),'-I'+str(src),
                    str(ROOT/'EZ80F910300ZCOG/src/uz.c'),
                    *[str(src/n) for n in ('tinflate.c','tinfgzip.c','tinfzlib.c','crc32.c','adler32.c')],
                    '-o',str(library)],check=True)
    lib=ctypes.CDLL(str(library));callback=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p)
    lib.uzipp.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t,callback]
    lib.uzipp.restype=ctypes.c_int
    calls=[]
    @callback
    def progress(pointer):calls.append(pointer);return 0
    def unpack(data,length,notify=False):
        output=ctypes.create_string_buffer(b'\xa5'*(length+16));source=ctypes.create_string_buffer(data)
        result=lib.uzipp(output,length,source,len(data),progress if notify else callback())
        assert output.raw[length:length+16]==b'\xa5'*16,'output overflow'
        return result,output.raw[:length]
    text=(ROOT/'CPM/CPM22_A.c').read_text();body=text[text.index('{')+1:text.index('}')]
    fixture=bytes(int(x,16) for x in re.findall(r'0x([0-9a-fA-F]{2})',body))
    expected=gzip.decompress(fixture);assert len(expected)==256256
    for notify in (False,True):
        result,actual=unpack(fixture,len(expected),notify)
        assert result==1 and actual==expected,(result,len(actual))
    assert len(calls)>=10
    bad=bytearray(fixture);bad[-5]^=0x80
    assert unpack(bytes(bad),len(expected))[0]==-4
    assert unpack(fixture[:-6],len(expected))[0]<0
    assert unpack(fixture,len(expected)-1)[0]<0
    assert unpack(fixture,len(expected)+1)[0]<0
    for payload in (b'A',b'12345',b''):
        packed=gzip.compress(payload)
        result,actual=unpack(packed,len(payload),True)
        assert result==1 and actual==payload,(result,payload)
    print('PASS: full 256256-byte CP/M disk, callback/null callback, CRC32, truncation, output bounds, tiny/empty streams')
