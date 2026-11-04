"""Framing-only hostile child; it implements no surface or browser policy."""
import json
import os
import struct
import sys
import time
mode = sys.argv[1]

def send(value):
    body=json.dumps(value).encode();sys.stdout.buffer.write(struct.pack('<I',len(body))+body);sys.stdout.buffer.flush()

while True:
    header=sys.stdin.buffer.read(4)
    if not header:break
    size=struct.unpack('<I',header)[0]
    frame=json.loads(sys.stdin.buffer.read(size))
    if frame['method']=='hello':
        send(dict(type='reply',id=frame['id'],ok=True,data=dict(protocolVersion=2,admissionSchema='machine-control-admission/v2')))
        if mode=='no-read':time.sleep(30)
        continue
    if mode=='timeout':time.sleep(30)
    elif mode=='bad-reply':send(dict(type='reply',id=frame['id'],ok=True,data=[]))
    elif mode=='partial':sys.stdout.buffer.write(b'\x10\x00');sys.stdout.buffer.flush();break
    elif mode=='environment':send(dict(type='reply',id=frame['id'],ok=True,data=dict(keys=sorted(os.environ))))
    elif mode=='stderr':
        os.write(2,b'x'*1048576)
        send(dict(type='reply',id=frame['id'],ok=True,data={}))
