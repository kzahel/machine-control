#!/usr/bin/env python3
"""Experimental Android transport using MC's existing Session and interpreter.

No desktop claims/audit equivalence is claimed. The native fixture grant and
exclusive connection are authoritative. This module never invokes ADB.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import json
import os
from pathlib import Path
import socket
import stat
import sys
from typing import Any

# During on-phone tests, client/ is staged beside this script, unchanged.
CLIENT = Path(__file__).resolve().parent / "client"
if not CLIENT.is_dir():
    CLIENT = Path(__file__).resolve().parents[3] / "client"
sys.path.insert(0, str(CLIENT))
from agent_session import Session, SessionError, Result, Capture, refusal
from agent_session_mcp import Namespace, BoundedOutput, Worker, MAX_REQUEST, MAX_REPLY

JSON = dict[str, Any]


class AndroidTransport:
    def __init__(self, receipt: Path) -> None:
        info = receipt.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid():
            raise SessionError("invalid_receipt", "Use an owned regular mode-0600 grant file")
        value = json.loads(receipt.read_text())
        if value.get("schema") != "mc-android-spike/v1":
            raise SessionError("invalid_receipt", "Unknown bridge grant schema")
        self.token = value["token"]
        self.generation = value["generation"]
        self.closed = False
        self.connection = socket.create_connection(("127.0.0.1", int(value["port"])), timeout=10)
        self.stream = self.connection.makefile("rwb")
        try:
            opened = self.call({"operation": "open"})
            if not opened.get("accepted"):
                raise refusal(opened)
        except BaseException:
            self.close()
            raise

    def call(self, request: JSON) -> JSON:
        if self.closed:
            raise SessionError("session_closed", "Reset explicitly; bridge connection ended")
        frame = json.dumps({**request, "token": self.token}).encode() + b"\n"
        if len(frame) > MAX_REQUEST:
            raise SessionError("request_too_large", "Android request exceeds 64 KiB")
        try:
            self.stream.write(frame)
            self.stream.flush()
            response = self.stream.readline(8 * 1024 * 1024 + 1)
            if not response.endswith(b"\n") or len(response) > 8 * 1024 * 1024:
                raise ValueError("Incomplete reply")
            result: JSON = json.loads(response)
            if result.get("generation") != self.generation:
                raise ValueError("Native generation changed")
            if not result.get("accepted"):
                # The bounded spike closes native ownership on every refusal.
                self.close()
            return result
        except (OSError, ValueError) as error:
            self.close()
            raise SessionError("bridge_lost", "Native reply unavailable; observe after explicit reset, never replay",
                               delivered="unknown") from error

    def image(self, result: JSON) -> bytes:
        return base64.b64decode(result["data"]["png"], validate=True)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.stream.close()
        self.connection.close()


def worker() -> int:
    config = json.loads(sys.stdin.buffer.readline(MAX_REQUEST + 1))
    session: Session | None = None
    transport: AndroidTransport | None = None
    namespace: Namespace | None = None
    try:
        for line in sys.stdin.buffer:
            if len(line) > MAX_REQUEST:
                return 2
            request = json.loads(line)
            output = BoundedOutput()
            images: list[JSON] = []
            error = False
            try:
                with contextlib.redirect_stdout(output):
                    if session is None:
                        transport = AndroidTransport(Path(config["receipt"]))
                        session = Session(transport, target="android-fixture", emit=print)
                        namespace = Namespace(session)
                    assert namespace is not None
                    session.emit_image = lambda data: images.append({"type": "image", "mimeType": "image/png",
                        "data": base64.b64encode(data).decode("ascii")})
                    if request.get("reset"):
                        namespace.reset()
                        print("Namespace reset; native connection retained.")
                    else:
                        value = namespace.run(request["code"])
                        if value is not None and not isinstance(value, (Result, Capture)):
                            print(value)
            except Exception as exc:
                error = True
                output.write(json.dumps({"code": getattr(exc, "code", type(exc).__name__),
                    "message": str(exc), "delivered": getattr(exc, "delivered", "unknown")}))
            closed = session.closed if session else False
            if transport is not None and transport.closed:
                closed = True
            reply = {"content": [{"type": "text", "text": output.getvalue() or "(no output)"}, *images],
                     "isError": error, "_sessionClosed": closed}
            encoded = json.dumps(reply)
            if len(encoded.encode()) > MAX_REPLY:
                encoded = json.dumps({"content": [{"type": "text", "text": "Reply limit exceeded"}],
                                      "isError": True, "_sessionClosed": closed})
            sys.stdout.write(encoded + "\n")
            sys.stdout.flush()
    finally:
        if session:
            session.close()
    return 0


HELP = """Fixture-only Android control using persistent Python. Variables persist;
calls block (no await). Start app = mc.app('MC Android Fixture'); inspect its
tree. app.tree(), app.set_value(n, text), app.press(n), app.screenshot().
Numbers come from the latest observation; never guess numbers. A screenshot
is viewable but coordinate actions are unsupported. Actions return delivery,
effect, uncertainty and a fresh tree. Confirm effects independently.
mc.close() releases native ownership. Reset clears variables; after transport
loss it opens new ownership without replaying code. This spike has a temporary
native fixture grant, not desktop claims/audit. Supply your published agent
session_id on every call; this is attribution, not bearer authority."""


def serve(receipt: Path) -> int:
    current: Worker | None = None
    owner: str | None = None
    tools = [{"name": "mc", "description": HELP, "inputSchema": {"type": "object", "properties": {
        "code": {"type": "string"}, "session_id": {"type": "string"}}, "required": ["code", "session_id"]}},
        {"name": "mc_reset", "description": "Reset this session explicitly.", "inputSchema": {
            "type": "object", "properties": {"session_id": {"type": "string"}}, "required": ["session_id"]}}]
    try:
        while line := sys.stdin.buffer.readline(MAX_REQUEST + 1):
            if len(line) > MAX_REQUEST:
                return 2
            request = json.loads(line)
            if "id" not in request:
                continue
            method = request.get("method")
            if method == "initialize":
                result = {"protocolVersion": request.get("params", {}).get("protocolVersion", "2025-06-18"),
                    "capabilities": {"tools": {}}, "serverInfo": {"name": "mc-android-spike", "version": "0.1"}}
            elif method == "tools/list":
                result = {"tools": tools}
            elif method == "ping":
                result = {}
            elif method == "tools/call":
                try:
                    params = request["params"]
                    arguments = params.get("arguments", {})
                    identity = arguments.get("session_id")
                    if not isinstance(identity, str) or not identity or len(identity) > 128 or owner not in (None, identity):
                        raise SessionError("session_identity_mismatch", "One interpreter per published agent session")
                    if params["name"] not in {"mc", "mc_reset"}:
                        raise SessionError("unsupported_tool", "Unknown tool")
                    owner = identity
                    reset = params["name"] == "mc_reset"
                    if current is None or (reset and current.closed):
                        current = Worker({"receipt": str(receipt)}, timeout=30,
                            command=[sys.executable, str(Path(__file__).resolve()), "--worker"])
                    result = current.request({"reset": True} if reset else {"code": arguments["code"]})
                except Exception as exc:
                    result = {"isError": True, "content": [{"type": "text", "text": json.dumps({
                        "code": getattr(exc, "code", type(exc).__name__), "message": str(exc)})}]}
            else:
                result = {"isError": True, "content": [{"type": "text", "text": "Unsupported method"}]}
            print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
    finally:
        if current:
            current.close()
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--worker"]:
        raise SystemExit(worker())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    raise SystemExit(serve(args.receipt))
