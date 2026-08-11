#!/usr/bin/env python3
"""Local browser fixture server with a file-backed effect oracle."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


STATE_PATH = Path.home() / ".cache/linuxvm-testbed/browser-fixture/state.json"
PAGE = b"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Machine Control Browser Fixture</title></head>
<body>
  <main>
    <h1>Machine Control Deterministic Browser Fixture</h1>
    <label>Browser text <input aria-label="Browser Fixture Text" id="text"></label>
    <button id="increment">Browser Semantic Increment</button>
    <canvas id="canvas" width="640" height="280"
      role="img" aria-label="Browser Visual Canvas"></canvas>
    <output id="status" aria-label="Browser Fixture Status">ready</output>
  </main>
  <script>
    const send = (event, value = null) => fetch('/effect', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({event, value})
    });
    document.querySelector('#increment').addEventListener('click', () => {
      send('semantic_press'); document.querySelector('#status').textContent = 'pressed';
    });
    document.querySelector('#text').addEventListener('input', event => {
      send('text_changed', event.target.value);
    });
    const canvas = document.querySelector('#canvas');
    const context = canvas.getContext('2d');
    context.fillStyle = '#141f33'; context.fillRect(0, 0, canvas.width, canvas.height);
    context.strokeStyle = '#33b2f2'; context.lineWidth = 4;
    context.strokeRect(24, 24, canvas.width - 48, canvas.height - 48);
    context.fillStyle = '#edf2ff'; context.font = '24px sans-serif';
    context.fillText('Browser custom-rendered visual fallback', 70, 145);
    canvas.addEventListener('click', event => send('visual_click', {
      x: event.offsetX, y: event.offsetY
    }));
  </script>
</body></html>
"""


class State:
    def __init__(self) -> None:
        self.value: dict[str, Any] = {
            "pid": os.getpid(),
            "sequence": 1,
            "semanticPresses": 0,
            "visualClicks": 0,
            "text": "",
            "lastEvent": "ready",
        }
        self.save()

    def save(self) -> None:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = STATE_PATH.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.value, separators=(",", ":"), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(STATE_PATH)

    def effect(self, event: str, value: Any) -> None:
        self.value["sequence"] += 1
        self.value["lastEvent"] = event
        if event == "semantic_press":
            self.value["semanticPresses"] += 1
        elif event == "visual_click":
            self.value["visualClicks"] += 1
            self.value["lastPointer"] = value
        elif event == "text_changed":
            self.value["text"] = str(value or "")
        self.save()


class Handler(BaseHTTPRequestHandler):
    state = State()

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(PAGE)))
            self.end_headers()
            self.wfile.write(PAGE)
            return
        if self.path == "/state":
            content = json.dumps(self.state.value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/effect":
            self.send_error(404)
            return
        length = min(int(self.headers.get("Content-Length", "0")), 65536)
        value = json.loads(self.rfile.read(length))
        self.state.effect(str(value.get("event") or ""), value.get("value"))
        self.send_response(204)
        self.end_headers()


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
