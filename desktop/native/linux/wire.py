"""Bounded JSON-line native/client transport; no authorization in framing."""
import json
from policy import decode

LIMIT=65536


def read_frame(stream,limit=LIMIT):
    body=stream.readline(limit+1)
    if not body:return None
    if len(body)>limit or not body.endswith(b'\n'):raise ValueError('frame_too_large')
    return decode(body)


def encode(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()+b'\n'


class SocketFrames:
    def __init__(self,client):self.client=client;self.buffer=bytearray()
    def readline(self,limit):
        while b'\n' not in self.buffer:
            if len(self.buffer)>=limit:raise ValueError('frame_too_large')
            chunk=self.client.recv(min(65536,limit-len(self.buffer)))
            if not chunk:return b''
            self.buffer.extend(chunk)
        line,_,self.buffer=self.buffer.partition(b'\n')
        if len(line)+1>limit:raise ValueError('frame_too_large')
        return bytes(line)+b'\n'
