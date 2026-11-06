"""Target-local HTTPS updater fixture for installed desktop update acceptance.

The installed app keeps its production endpoint. The caller temporarily maps
that host to loopback and trusts a fixture CA inside a disposable target, then
serves the exact candidate's release-staged latest.json and signed installer.
Older current versions receive the update; equal or newer receive 204.
While --tamper-flag exists, installer bytes are modified to prove that a
rejected download never interrupts access. Logs contain paths and headers only.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import ssl
import time


def version(value):
    if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value):
        raise ValueError('Expected MAJOR.MINOR.PATCH')
    return tuple(map(int, value.split('.')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cert', type=Path, required=True)
    parser.add_argument('--key', type=Path, required=True)
    parser.add_argument('--latest', type=Path, required=True, help='release-staged latest.json with fixture URLs')
    parser.add_argument('--installer', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--tamper-flag', type=Path)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=443)
    args = parser.parse_args()
    latest = json.loads(args.latest.read_text(encoding='utf-8'))
    available = version(latest['version'])
    body = json.dumps(latest).encode()
    installer = args.installer.read_bytes()
    route = '/fixture/' + args.installer.name.replace(' ', '%20')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def record(self, status, size=0, tampered=False):
            entry = {'at': time.time(), 'method': self.command, 'path': self.path, 'status': status,
                     'bytes': size, 'tampered': tampered, 'checkReason': self.headers.get('X-Check-Reason'),
                     'userAgent': self.headers.get('User-Agent')}
            with args.log.open('a', encoding='utf-8') as log:
                log.write(json.dumps(entry) + '\n')

        def send(self, status, payload=b'', kind='application/json', tampered=False):
            self.send_response(status)
            if status != 204:
                self.send_header('Content-Type', kind)
                self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if status != 204:
                self.wfile.write(payload)
            self.record(status, len(payload), tampered)

        def do_GET(self):
            match = re.fullmatch(r'/updates/tauri/(windows)/(aarch64|x86_64)/([0-9.]+)', self.path)
            if match:
                try:
                    current = version(match[3])
                except ValueError:
                    return self.send(404, b'Unsupported update target', 'text/plain')
                return self.send(200, body) if current < available else self.send(204)
            if self.path == route:
                tampered = bool(args.tamper_flag and args.tamper_flag.exists())
                return self.send(200, installer + (b'tampered' if tampered else b''),
                                 'application/octet-stream', tampered)
            self.send(404, b'Not found', 'text/plain')

    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(args.cert, args.key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
