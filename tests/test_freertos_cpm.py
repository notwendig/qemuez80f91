#!/usr/bin/env python3
"""Live test: a running FreeRTOS target must boot CP/M and accept DIR twice.

Usage: python3 tests/test_freertos_cpm.py 192.168.77.26 [4050]
The initial guest-side gzip decompression can take several minutes.
"""
import socket
import sys
import time

host=sys.argv[1];port=int(sys.argv[2]) if len(sys.argv)>2 else 4050
for attempt in range(2):
    deadline=time.monotonic()+90
    while True:
        try:
            client=socket.create_connection((host,port),timeout=3)
            break
        except OSError:
            if time.monotonic()>deadline:raise
            time.sleep(1)
    with client:
        client.settimeout(1)
        if attempt:client.sendall(b'\r')
        def prompt(timeout):
            output=bytearray();end=time.monotonic()+timeout
            while time.monotonic()<end:
                try:chunk=client.recv(8192)
                except socket.timeout:continue
                if not chunk:raise AssertionError('CP/M disconnected')
                output+=chunk
                print(chunk.decode('latin1'),end='',flush=True)
                if b'a>' in output.lower() or b'a0>' in output.lower():return output
            raise AssertionError('CP/M prompt timeout: '+repr(output[-500:]))
        prompt(420 if not attempt else 60)
        client.sendall(b'DIR\r')
        listing=prompt(90)
        assert b'COM' in listing.upper(),listing
        print('\nPASS: CP/M '+('reconnect' if attempt else 'boot')+' and DIR',flush=True)
    time.sleep(2)
