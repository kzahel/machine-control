"""Small stdio MCP facade with a killable, persistent Python worker.

Agent code has the ordinary client process's privileges. This is execution
isolation for timeouts and ownership cleanup, not a same-user security sandbox.
"""
from __future__ import annotations

import argparse
import ast
import base64
import contextlib
import io
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
from typing import Any, Callable, TextIO, cast

import audit_history
import machine_control as common
from agent_session import JSON, Result, Session, SessionError, Stopped, SessionTimeout
from agent_session_transport import RetainedTransport

HELP = """Persistent Python desktop session. Calls are blocking: do not write await.
mc.apps(), mc.windows(), mc.state(), mc.app(exact_name_or_id), mc.launch(app_id).
Bind app = mc.app("TextEdit"); it prints an initial tree.
app.tree(query=None, full=False), app.press(n), app.click(n), app.focus(n),
app.set_value(n, text), app.key("cmd+s"), app.type(text), app.choose(absolute_path),
app.screenshot(). Actions print route/delivery/effect/uncertainty and a fresh tree.
Numbers belong to that app's latest observation. Removed or replaced numbers
are stale; never guess a new number. Query menus with app.tree(query="Save").
Use app.choose(path) for a native Open/Save panel; inspect any follow-up sheet.
Accepted delivery is not proof of the requested effect. Inspect results.
The final expression and print output are shown. Variables persist between calls.
Reset clears variables and numbers but keeps the live claim and open apps.
Session owns a target claim, normal resident admission and per-operation audit.
An admission is bounded to 15 minutes; an expired/stopped owner is not replayed
or silently replaced. A timeout stops the worker and its live ownership; use
reset explicitly before starting fresh. No fixed agent sleeps are needed.
"""
MAX_REQUEST = 65536
MAX_REPLY = 12 * 1024 * 1024
MAX_TEXT = 24000


class BoundedOutput(io.StringIO):
    def write(self, value: str) -> int:
        if self.tell() + len(value) > MAX_TEXT:
            super().write(value[:max(0, MAX_TEXT - self.tell())])
            raise SessionError("output_limit", "Output truncated at 24000 characters; earlier effects may have occurred. Narrow the observation.", delivered="unknown")
        return super().write(value)


class Namespace:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.values: dict[str, Any] = {"mc": session}

    def reset(self) -> None:
        for app in self.session.handles:
            app.invalidate()
        self.session.handles.clear()
        self.values = {"mc": self.session}

    def run(self, code: str) -> object:
        parsed = ast.parse(code, filename="<mc-session>", mode="exec")
        final: ast.expr | None = None
        if parsed.body and isinstance(parsed.body[-1], ast.Expr):
            final = parsed.body[-1].value
            parsed.body.pop()
        exec(compile(parsed, "<mc-session>", "exec"), self.values)
        return eval(compile(ast.Expression(final), "<mc-session>", "eval"), self.values) if final else None


def worker() -> int:
    configured = sys.stdin.buffer.readline(MAX_REQUEST + 1)
    if len(configured) > MAX_REQUEST:
        return 2
    config = json.loads(configured)
    session: Session | None = None
    namespace: Namespace | None = None
    try:
        while line := sys.stdin.buffer.readline(MAX_REQUEST + 1):
            if len(line) > MAX_REQUEST:
                return 2
            request = json.loads(line)
            output = BoundedOutput()
            images: list[JSON] = []
            is_error = False
            error: JSON | None = None
            action_start = session.action_attempts if session else 0
            try:
                with contextlib.redirect_stdout(output):
                    if session is None:
                        transport = RetainedTransport(config["alias"], config["target"],
                            reason=config["reason"], claimant_authority=config["claimantAuthority"],
                            claimant_id=config["claimantId"])
                        session = Session(transport, target=config["alias"], emit=lambda value: print(value),
                            auto_observe=config.get("autoObserve", True))
                        namespace = Namespace(session)
                    assert namespace is not None
                    session.emit_image = lambda data: images.append({"type": "image", "mimeType": "image/png",
                                                                    "data": base64.b64encode(data).decode("ascii")})
                    if request.get("reset"):
                        namespace.reset()
                        print("Namespace reset; the live claim and application state are retained.")
                    else:
                        value = namespace.run(request["code"])
                        if value is not None and not isinstance(value, Result):
                            print(value)
            except SessionError as exc:
                is_error = True
                error = {"code": exc.code, "delivered": exc.delivered, "retryable": exc.retryable,
                         "message": str(exc)}
            except Exception as exc:
                is_error = True
                error = {"code": type(exc).__name__, "message": str(exc)}
            body = output.getvalue()
            if error:
                error["actionAttemptsInSnippet"] = session.action_attempts - action_start if session else 0
                body += "\n" + json.dumps(error, ensure_ascii=False)
            response = {"content": [{"type": "text", "text": body or "(no output)"}, *images],
                        "isError": is_error}
            encoded = json.dumps(response)
            if len(encoded.encode()) > MAX_REPLY:
                encoded = json.dumps({"content": [{"type": "text", "text": "Reply exceeded 12 MiB; use one capture per call."}], "isError": True})
            sys.stdout.write(encoded + "\n")
            sys.stdout.flush()
    finally:
        if session:
            session.close()
    return 0


class Worker:
    def __init__(self, config: JSON, *, timeout: float = 180,
                 command: list[str] | None = None) -> None:
        self.timeout = timeout
        self.process = subprocess.Popen(command or [sys.executable, str(Path(__file__).resolve()), "--worker"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, start_new_session=True)
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write(json.dumps(config).encode() + b"\n")
        self.process.stdin.flush()
        self.replies: queue.Queue[bytes] = queue.Queue(maxsize=1)
        self.closed = False
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self) -> None:
        assert self.process.stdout is not None
        try:
            while not self.closed:
                line = self.process.stdout.readline(MAX_REPLY + 1)
                self.replies.put(line)
                if not line or len(line) > MAX_REPLY:
                    return
        except (OSError, ValueError):
            if not self.closed:
                self.replies.put(b"")

    def request(self, value: JSON) -> JSON:
        if self.closed:
            raise Stopped("session_stopped", "Reset explicitly before starting a new session")
        encoded = json.dumps(value).encode() + b"\n"
        if len(encoded) > MAX_REQUEST:
            raise SessionError("request_too_large", "Snippet request exceeds 64 KiB")
        try:
            assert self.process.stdin is not None
            self.process.stdin.write(encoded)
            self.process.stdin.flush()
            response = self.replies.get(timeout=self.timeout)
            if not response or len(response) > MAX_REPLY:
                raise SessionError("worker_lost", "Worker ended or exceeded its output bound", delivered="unknown")
            value = json.loads(response)
            if not isinstance(value, dict) or not isinstance(value.get("content"), list):
                raise ValueError("Malformed worker reply")
            return value
        except queue.Empty as exc:
            self.close()
            raise SessionTimeout("snippet_timeout", "Worker stopped; effects may have occurred. Observe after explicit reset.", delivered="unknown") from exc
        except (OSError, ValueError, SessionError) as exc:
            self.close()
            if isinstance(exc, SessionError):
                raise
            raise SessionError("worker_lost", "Worker reply unavailable; observe before retry", delivered="unknown") from exc

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.process.stdout:
            self.process.stdout.close()


def serve(alias: str, target: JSON, arguments: list[str], *,
          incoming: TextIO = sys.stdin, outgoing: TextIO = sys.stdout,
          worker_factory: Callable[..., Worker] = Worker) -> int:
    parser = argparse.ArgumentParser(prog="machine-control mcp")
    parser.add_argument("--reason", default="Perform the requested desktop task")
    parser.add_argument("--claimant-authority")
    parser.add_argument("--claimant-id")
    parser.add_argument("--observe", choices=("action", "explicit"), default="action")
    options = parser.parse_args(arguments)
    reference = cast(Callable[[], JSON | None], audit_history.session_ref)()
    authority, claimant = options.claimant_authority, options.claimant_id
    if authority is None and claimant is None and reference:
        authority = common.CLAIMANT_AUTHORITIES[reference["source"]]
        claimant = reference["id"]
    config = {"alias": alias, "target": target, "reason": options.reason,
              "claimantAuthority": authority, "claimantId": claimant,
              "autoObserve": options.observe == "action"}
    current: Worker | None = None
    tools = [{"name": "mc", "description": HELP,
              "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}},
                              "required": ["code"], "additionalProperties": False}},
             {"name": "mc_reset", "description": "Clear Python variables and element numbers. Keeps live ownership; after a stopped worker, explicitly starts a fresh admitted session.",
              "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}}]
    try:
        while line := incoming.readline(MAX_REQUEST + 1):
            request_id: object = None
            try:
                if len(line.encode()) > MAX_REQUEST:
                    raise ValueError("Request exceeds 64 KiB")
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError("Request must be an object")
                request_id = request.get("id")
                if "id" not in request:
                    continue
                method = request.get("method")
                result: JSON
                if method == "initialize":
                    result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                              "serverInfo": {"name": "machine-control-python", "version": "0.1.0"}}
                elif method == "ping":
                    result = {}
                elif method == "tools/list":
                    result = {"tools": tools}
                elif method == "tools/call":
                    params = request.get("params", {})
                    name, args = params.get("name"), params.get("arguments", {})
                    if name not in {"mc", "mc_reset"} or not isinstance(args, dict):
                        raise ValueError("Unknown tool or malformed arguments")
                    if name == "mc" and (set(args) != {"code"} or not isinstance(args["code"], str)):
                        raise ValueError("mc requires only a code string")
                    if name == "mc_reset" and args:
                        raise ValueError("mc_reset takes no arguments")
                    try:
                        if not authority or not claimant:
                            raise SessionError("claimant_required", "Provide truthful claimant arguments outside an agent host")
                        if current is None or name == "mc_reset" and current.closed:
                            if current:
                                current.close()
                            current = worker_factory(config)
                        result = current.request({"reset": True} if name == "mc_reset" else args)
                    except SessionError as exc:
                        result = {"content": [{"type": "text", "text": json.dumps({"code": exc.code,
                                  "delivered": exc.delivered, "retryable": exc.retryable, "message": str(exc)})}], "isError": True}
                else:
                    raise ValueError("Unsupported MCP method")
                response = {"jsonrpc": "2.0", "id": request_id, "result": result}
            except (ValueError, TypeError, AttributeError) as exc:
                response = {"jsonrpc": "2.0", "id": request_id,
                            "error": {"code": -32600, "message": str(exc)}}
            outgoing.write(json.dumps(response) + "\n")
            outgoing.flush()
    finally:
        if current:
            current.close()
    return 0


if __name__ == "__main__":
    if sys.argv[1:] != ["--worker"]:
        raise SystemExit("Use bin/machine-control --target TARGET mcp")
    raise SystemExit(worker())
