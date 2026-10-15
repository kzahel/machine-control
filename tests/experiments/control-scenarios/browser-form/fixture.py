#!/usr/bin/env python3
"""Held-out form fixture; page actions produce an independent server receipt.

No browser is launched here. A future authorized harness owns the loopback
server, separately identified test browser, process cleanup and fixture root.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs


def setup(root, seed):
    root.mkdir(parents=True, exist_ok=False)
    nonce = hashlib.sha256(seed.encode()).hexdigest()
    expected = {'nonce': nonce, 'name': 'Review ' + nonce[:8], 'category': 'review', 'consent': 'yes'}
    (root/'expected.json').write_text(json.dumps(expected))
    (root/'index.html').write_text('''<!doctype html><title>Held-out review</title>
<p>Requested review name: Review ''' + nonce[:8] + '''</p>
<form method="post" action="/submit">
<label>Review name <input name="name" required></label>
<label>Category <select name="category"><option value="draft">Draft</option>
<option value="review">Ready for review</option></select></label>
<label><input type="checkbox" name="consent" value="yes">Confirm review</label>
<input type="hidden" name="nonce" value="''' + nonce + '''">
<button type="submit">Submit review</button></form>''')


def observe_submission(root, body):
    """Server-only witness; do not expose the receipt path as an action API."""
    fields = parse_qs(body, keep_blank_values=True, strict_parsing=True)
    values = {key: items[0] if len(items) == 1 else items for key, items in fields.items()}
    events = root/'submissions.jsonl'
    with events.open('a') as stream:
        stream.write(json.dumps(values) + '\n')


def oracle(root):
    expected = json.loads((root/'expected.json').read_text())
    path = root/'submissions.jsonl'
    try:
        events = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    except (ValueError, OSError):
        events = []
    return {'passed': events == [expected], 'detail': 'Exactly one server-observed matching submission required'}


def serve(root, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path != '/':
                self.send_error(404)
                return
            data = (root/'index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            length = int(self.headers.get('Content-Length', '0'))
            if self.path != '/submit' or not 0 < length <= 4096:
                self.send_error(400)
                return
            observe_submission(root, self.rfile.read(length).decode())
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'Submission recorded')
    server = HTTPServer(('127.0.0.1', port), Handler)
    (root/'server.json').write_text(json.dumps({'url': f'http://127.0.0.1:{server.server_port}/'}))
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('setup', 'oracle', 'serve'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--seed', default='fixture')
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    if args.operation == 'setup':
        setup(args.root, args.seed)
    elif args.operation == 'oracle':
        print(json.dumps(oracle(args.root)))
    else:
        serve(args.root, args.port)
