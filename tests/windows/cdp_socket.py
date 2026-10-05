"""Small standard-library tab-level CDP client for the bounded live fixture."""
import base64
import hashlib
import json
import os
import socket
import struct
from urllib.parse import urlsplit


class CdpSocket:
    def __init__(self, url, origin=None):
        parts = urlsplit(url)
        if parts.scheme != 'ws' or parts.hostname != '127.0.0.1':
            raise ValueError('Fixture requires target loopback')
        self.socket = socket.create_connection((parts.hostname, parts.port), timeout=5)
        self.events = []
        self.next_id = 0
        key = base64.b64encode(os.urandom(16)).decode()
        request = (f'GET {parts.path}?{parts.query} HTTP/1.1\r\n'
                   f'Host: 127.0.0.1:{parts.port}\r\nUpgrade: websocket\r\n'
                   f'Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: {key}\r\n')
        if origin is not None:
            request += f'Origin: {origin}\r\n'
        try:
            self.socket.sendall((request + '\r\n').encode('ascii'))
            header = bytearray()
            while not header.endswith(b'\r\n\r\n'):
                header.extend(self._exact(1))
                if len(header) > 8192:
                    raise ValueError('Oversized handshake')
            expected = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
            if not header.startswith(b'HTTP/1.1 101 ') or f'Sec-WebSocket-Accept: {expected}'.encode() not in header:
                raise ConnectionError('Upgrade refused')
        except BaseException:
            self.socket.close()
            raise

    def _exact(self, count):
        value = bytearray()
        while len(value) < count:
            block = self.socket.recv(count - len(value))
            if not block:
                raise ConnectionError('CDP socket closed')
            value.extend(block)
        return bytes(value)

    def send(self, payload, opcode=1):
        body = payload.encode() if isinstance(payload, str) else payload
        mask = os.urandom(4)
        length = len(body)
        header = bytes([0x80 | opcode, 0x80 | (length if length < 126 else 126 if length < 65536 else 127)])
        if length >= 65536:
            header += struct.pack('!Q', length)
        elif length >= 126:
            header += struct.pack('!H', length)
        self.socket.sendall(header + mask + bytes(byte ^ mask[i % 4] for i, byte in enumerate(body)))

    def read(self):
        body = bytearray()
        while True:
            first, second = self._exact(2)
            opcode = first & 15
            length = second & 127
            if second & 128:
                raise ValueError('Server frame must be unmasked')
            if length == 126:
                length = struct.unpack('!H', self._exact(2))[0]
            elif length == 127:
                length = struct.unpack('!Q', self._exact(8))[0]
            if length + len(body) > 16 * 1024 * 1024:
                raise ValueError('Oversized CDP result')
            data = self._exact(length)
            if opcode == 8:
                raise ConnectionError('CDP session closed')
            if opcode == 9:
                self.send(data, 10)
                continue
            if opcode == 10:
                continue
            if opcode not in (0, 1):
                raise ValueError('Text CDP frame required')
            body.extend(data)
            if first & 128:
                return json.loads(body)

    def call(self, method, params=None, session_id=None):
        self.next_id += 1
        self.send(json.dumps({'id': self.next_id, 'method': method, 'params': params or {},
                             **({'sessionId': session_id} if session_id else {})}))
        while True:
            message = self.read()
            if message.get('id') == self.next_id:
                return message
            self.events.append(message)

    def event(self, method):
        while True:
            for i, message in enumerate(self.events):
                if message.get('method') == method:
                    return self.events.pop(i)
            self.events.append(self.read())

    def close(self):
        self.socket.close()
