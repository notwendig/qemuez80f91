#!/usr/bin/env python3
"""Live FreeRTOS kit test: ISR, debounce task, and all three button counters.
Usage: python3 tests/test_freertos_buttons.py /tmp/ez80f91-1000/4040.qmp
Requires the running firmware to match the project's current ZDS map.
"""
from pathlib import Path
import re
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from kit import KitControls
root=Path(__file__).resolve().parents[1]
mapfile=root/'subprojects/FreeRTOS-eZ80f91/bin/EZ80F910300ZCOGd.map'
address=int(re.search(r'^_get_button\s+C:([0-9A-F]+)',mapfile.read_text(),re.M)[1],16)
control=KitControls(Path(sys.argv[1]))
with tempfile.TemporaryDirectory(prefix='f91-live-buttons-') as td:
    target=Path(td)/'memory'
    def memory(at,size):
        control.request('pmemsave',{'val':at,'size':size,'filename':str(target)})
        return target.read_bytes()
    # ZDS get_button: multiply id by sizeof(button_t), add the static array.
    code=memory(address,32)
    base=int.from_bytes(re.search(rb'\x01(.{3})\x09\xdd\xf9',code,re.S)[1],'little')
    def buttons():
        data=memory(base,63)
        return [(int.from_bytes(data[i+3:i+6],'little'),
                 int.from_bytes(data[i+12:i+15],'little')) for i in (0,21,42)]
    def wait(state,counts=None):
        end=time.monotonic()+30
        while time.monotonic()<end:
            result=buttons()
            if all(s==state and (counts is None or n>old)
                   for (s,n),old in zip(result,counts or [0,0,0])):
                return result
            time.sleep(.1)
        raise AssertionError(('debounced buttons did not update',state,result,counts))
    initial=wait(1)
    try:
        for bit in range(3):control.button(bit,True)
        down=wait(0,[n for s,n in initial])
        print('PASS: SW1..3 pressed, debounced states and counters:',down,flush=True)
    finally:control.release()
    up=wait(1,[n for s,n in down])
    print('PASS: SW1..3 released, debounced states and counters:',up,flush=True)
    assert control.request('query-status')['running']
