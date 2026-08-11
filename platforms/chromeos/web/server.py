#!/usr/bin/env python3
"""
Remote desktop server for ChromeOS testbed.

Serves the web UI and forwards mouse/keyboard/scroll input to the Chromebook
by calling bin/chromeos commands over SSH.

Usage:
    python3 web/server.py [port]         # default port 8765
    bin/chromeos remote-desktop [port]   # convenience wrapper

Then open http://localhost:8765 in your browser and select the Cam Link 4K.
"""

import json
import os
import subprocess
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMEOS_BIN = os.path.join(REPO_DIR, 'bin', 'chromeos')
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PORT = 8765


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/index.html'):
            self._serve_file('index.html', 'text/html; charset=utf-8')
        elif path == '/info':
            self._serve_info()
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == '/event':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                event = json.loads(body)
                result = self._handle_event(event)
                self._json_response(result)
            except Exception as e:
                self._json_response({'error': str(e)}, 500)
        else:
            self.send_error(404)

    def _serve_file(self, filename, content_type):
        filepath = os.path.join(WEB_DIR, filename)
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_info(self):
        try:
            result = subprocess.run(
                [CHROMEOS_BIN, 'info'],
                capture_output=True, text=True, timeout=15,
            )
            data = result.stdout.strip()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data.encode())))
            self.end_headers()
            self.wfile.write(data.encode())
        except Exception as e:
            self._json_response({'error': str(e)}, 500)

    def _handle_event(self, event):
        etype = event.get('type')

        if etype == 'tap':
            x = int(round(event['x']))
            y = int(round(event['y']))
            args = [CHROMEOS_BIN, 'tap', str(x), str(y)]
            print(f'tap ({x}, {y})', flush=True)
            r = subprocess.run(args, capture_output=True, text=True, timeout=10)
            ok = r.returncode == 0
            if not ok:
                print(f'  tap FAILED rc={r.returncode} stderr={r.stderr.strip()!r}', flush=True)
            return {'ok': ok}

        elif etype == 'swipe':
            x1, y1 = int(round(event['x1'])), int(round(event['y1']))
            x2, y2 = int(round(event['x2'])), int(round(event['y2']))
            duration = int(event.get('duration_ms', 200))
            args = [CHROMEOS_BIN, 'swipe', str(x1), str(y1), str(x2), str(y2), str(duration)]
            print(f'swipe ({x1},{y1})→({x2},{y2}) {duration}ms', flush=True)
            r = subprocess.run(args, capture_output=True, text=True, timeout=10)
            ok = r.returncode == 0
            if not ok:
                print(f'  swipe FAILED rc={r.returncode} stderr={r.stderr.strip()!r}', flush=True)
            return {'ok': ok}

        elif etype == 'type':
            text = event.get('text', '')
            if not text:
                return {'ok': True}
            print(f'type {text!r}', flush=True)
            r = subprocess.run(
                [CHROMEOS_BIN, 'type', text],
                capture_output=True, text=True, timeout=10,
            )
            ok = r.returncode == 0
            if not ok:
                print(f'  type FAILED rc={r.returncode} stderr={r.stderr.strip()!r}', flush=True)
            return {'ok': ok}

        elif etype == 'shortcut':
            mods = event.get('mods', [])
            key = event.get('key', '')
            if not key:
                return {'error': 'missing key'}
            args = [CHROMEOS_BIN, 'shortcut'] + mods + [key]
            print(f'shortcut {" ".join(mods + [key])}', flush=True)
            r = subprocess.run(args, capture_output=True, text=True, timeout=10)
            ok = r.returncode == 0
            if not ok:
                print(f'  shortcut FAILED rc={r.returncode} stderr={r.stderr.strip()!r}', flush=True)
            return {'ok': ok}

        elif etype == 'mouse_move':
            x = int(round(event['x']))
            y = int(round(event['y']))
            r = subprocess.run(
                [CHROMEOS_BIN, 'mouse-move', str(x), str(y)],
                capture_output=True, text=True, timeout=10,
            )
            ok = r.returncode == 0
            if not ok:
                print(f'  mouse-move FAILED rc={r.returncode} stderr={r.stderr.strip()!r}', flush=True)
            return {'ok': ok}

        elif etype == 'mouse_click':
            button = event.get('button', 'left')
            x = event.get('x')
            y = event.get('y')
            args = [CHROMEOS_BIN, 'mouse-click', button]
            if x is not None and y is not None:
                args += [str(int(round(x))), str(int(round(y)))]
            print(f'mouse_click {button} ({x}, {y})', flush=True)
            r = subprocess.run(args, capture_output=True, text=True, timeout=10)
            ok = r.returncode == 0
            if not ok:
                print(f'  mouse-click FAILED rc={r.returncode} stderr={r.stderr.strip()!r}', flush=True)
            return {'ok': ok}

        elif etype == 'mouse_scroll':
            delta = int(event.get('delta', 0))
            if not delta:
                return {'ok': True}
            print(f'mouse_scroll {delta}', flush=True)
            r = subprocess.run(
                [CHROMEOS_BIN, 'mouse-scroll', str(delta)],
                capture_output=True, text=True, timeout=10,
            )
            ok = r.returncode == 0
            if not ok:
                print(f'  mouse-scroll FAILED rc={r.returncode} stderr={r.stderr.strip()!r}', flush=True)
            return {'ok': ok}

        else:
            print(f'unknown event type: {etype!r}', flush=True)
            return {'error': f'unknown event type: {etype!r}'}

    def _json_response(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Only log non-event requests (keep event stream clean)
        if '/event' not in fmt % args:
            print(self.address_string(), fmt % args, flush=True)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    url = f'http://localhost:{port}'
    print(f'Remote desktop: {url}')
    print(f'Open {url} in your browser, then select the Cam Link 4K.')
    print('Ctrl+C to stop.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nDone.')
