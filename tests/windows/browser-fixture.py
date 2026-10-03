"""Target-local browser oracle; its file effect is independent of CDP replies."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

PAGE = b'''<!doctype html><meta charset="utf-8"><title>Machine Control Browser Fixture</title>
<label>Message <input id="message" aria-label="Message"></label>
<button onclick="effect('increment')">Increment browser counter</button>
<button onclick="effect('message')">Save message</button>
<a href="/next">Next page</a><output id="status"></output>
<script>async function effect(action){let r=await fetch('/effect',{method:'POST',body:JSON.stringify({action,value:document.querySelector('#message').value})});document.querySelector('#status').textContent=JSON.stringify(await r.json())}</script>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--marker', required=True, type=Path)
    parser.add_argument('--port-file', required=True, type=Path)
    args = parser.parse_args()
    state = {'counter': 0, 'message': ''}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *values):
            pass

        def do_GET(self):
            page = PAGE if self.path == '/' else b'<title>Next fixture page</title><p>Navigation confirmed</p>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def do_POST(self):
            size = int(self.headers.get('Content-Length', '0'))
            if self.path != '/effect' or not 1 <= size <= 4096:
                self.send_error(400)
                return
            request = json.loads(self.rfile.read(size))
            if request.get('action') == 'increment':
                state['counter'] += 1
            elif request.get('action') == 'message':
                state['message'] = str(request.get('value', ''))
            else:
                self.send_error(400)
                return
            args.marker.with_suffix('.new').write_text(json.dumps(state), encoding='utf-8')
            args.marker.with_suffix('.new').replace(args.marker)
            data = json.dumps(state).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    args.marker.write_text(json.dumps(state), encoding='utf-8')
    args.port_file.write_text(str(server.server_port), encoding='ascii')
    server.serve_forever()


if __name__ == '__main__':
    main()
