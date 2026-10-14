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
import os
from pathlib import Path
import queue
import re
import stat
import subprocess
import sys
import threading
from typing import Any, Callable, TextIO, cast

import audit_history
import machine_control as common
from agent_session import JSON, Capture, Result, Session, SessionError, Stopped, SessionTimeout
from agent_session_transport import RetainedTransport

HELP = """Persistent Python desktop session. Calls are blocking: do not write await.
Every call requires session_id: your published agent session ID. If unknown,
read AGENTCTL_SESSION_ID, CLAUDE_CODE_SESSION_ID or CODEX_THREAD_ID in your shell.
This is self-asserted audit attribution, not a secret or bearer authority.
mc.apps(), mc.windows(), mc.state(), mc.app(exact_name_or_id), mc.launch(app_id).
Bind app = mc.app("TextEdit"); it prints an initial tree.
app.tree(query=None, full=False), app.press(n), app.click(n), app.focus(n),
app.set_value(n, text), app.key("cmd+s"), app.type(text), app.choose(absolute_path),
app.scroll(n,"down",pixels=400). shot = app.screenshot() attaches a window image;
shot.click(x,y) and shot.scroll(x,y,"down",pixels=400) use IMAGE pixels. Capture
coordinates check the same window/geometry and expire after any action. Capture
again before another coordinate action. These pointer routes move the cursor.
Actions print route/delivery/effect/uncertainty and a fresh tree.
Numbers belong to that app's latest observation. Removed or replaced numbers
are stale; never guess a new number. Query menus with app.tree(query="Save").
Use app.choose(path) for a native Open/Save panel; inspect any follow-up sheet.
Accepted delivery is not proof of the requested effect. Inspect results.
The final expression and print output are shown. Variables persist between calls.
When the task is finished, call mc.close() to release its claim and admission.
You may put that call at the end of the final code snippet; open apps remain.
Reset clears variables and numbers but keeps the live claim and open apps.
Session owns a target claim, normal resident admission and per-operation audit.
An admission is bounded to 15 minutes; an expired/stopped owner is not replayed
or silently replaced. A timeout stops the worker and its live ownership; use
reset explicitly before starting fresh. No fixed agent sleeps are needed.
"""
MAX_REQUEST = 65536
MAX_REPLY = 12 * 1024 * 1024
MAX_TEXT = 24000
SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


def published_session(path: Path) -> str:
    """Read an explicit coordinator publication, never search other sessions."""
    try:
        path = path.expanduser()
        if path.is_symlink():
            raise ValueError("Session publication must not be a symbolic link")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError("Expected a regular mode-0600 session publication")
            identifier = stream.read(130).decode("ascii").strip()
            if not SESSION_ID.fullmatch(identifier):
                raise ValueError("Invalid published session ID")
            return identifier
    except (OSError, ValueError) as exc:
        raise SessionError("session_identity_unavailable", "Coordinator session publication is not ready; no target operation was sent",
                           retryable=True) from exc


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
    startup_failed = False
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
                    if request.get("reset"):
                        startup_failed = False
                    if startup_failed:
                        raise Stopped("session_start_failed", "Reset explicitly after resolving the previous startup refusal")
                    if session is None:
                        transport = RetainedTransport(config["alias"], config["target"],
                            reason=config["reason"], claimant_authority=config["claimantAuthority"],
                            claimant_id=config["claimantId"], session_id=config["sessionId"])
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
                        if value is not None and not isinstance(value, (Result, Capture)):
                            print(value)
            except SessionError as exc:
                startup_failed = session is None
                is_error = True
                error = {"code": exc.code, "delivered": exc.delivered, "retryable": exc.retryable,
                         "message": str(exc)}
            except common.ClientError as exc:
                startup_failed = session is None
                is_error = True
                error = {"code": exc.code, "delivered": "no" if session is None else "unknown", "message": str(exc)}
            except Exception as exc:
                startup_failed = session is None
                is_error = True
                error = {"code": type(exc).__name__, "message": str(exc)}
            body = output.getvalue()
            if error:
                error["actionAttemptsInSnippet"] = session.action_attempts - action_start if session else 0
                body += "\n" + json.dumps(error, ensure_ascii=False)
            response = {"content": [{"type": "text", "text": body or "(no output)"}, *images],
                        "isError": is_error, "_sessionClosed": session.closed if session else False}
            encoded = json.dumps(response)
            if len(encoded.encode()) > MAX_REPLY:
                encoded = json.dumps({"content": [{"type": "text", "text": "Reply exceeded 12 MiB; use one capture per call."}],
                                      "isError": True, "_sessionClosed": session.closed if session else False})
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
            if value.pop("_sessionClosed", False):
                self.close()
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
            try:
                self.process.stdin.close()
            except OSError:
                pass
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
    parser.add_argument("--session-id-file", type=Path,
                        help="Explicit mode-0600 coordinator publication of this agent's session ID")
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
    owner_id: str | None = None
    session_property = {"type": "string", "description": "Your published agent session ID; use the same ID on every call.",
                        "pattern": SESSION_ID.pattern}
    help_text = HELP
    if options.session_id_file:
        help_text = help_text.replace(
            "Every call requires session_id: your published agent session ID. If unknown,\n"
            "read AGENTCTL_SESSION_ID, CLAUDE_CODE_SESSION_ID or CODEX_THREAD_ID in your shell.\n",
            "Your coordinator supplies the published agent session ID; omit session_id.\n")
    required_identity = [] if options.session_id_file else ["session_id"]
    tools = [{"name": "mc", "description": help_text,
              "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "session_id": session_property},
                              "required": ["code", *required_identity], "additionalProperties": False}},
             {"name": "mc_reset", "description": "Clear Python variables and element numbers. Keeps live ownership; after a stopped worker, explicitly starts a fresh admitted session.",
              "inputSchema": {"type": "object", "properties": {"session_id": session_property},
                              "required": required_identity, "additionalProperties": False}}]
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
                    identity_keys = {"session_id"} if not options.session_id_file else set()
                    if name == "mc" and (not {"code", *identity_keys} <= set(args) or
                                         set(args) - {"code", "session_id"} or not isinstance(args["code"], str)):
                        raise ValueError("mc requires code and session_id strings")
                    if name == "mc_reset" and (not identity_keys <= set(args) or set(args) - {"session_id"}):
                        raise ValueError("mc_reset requires session_id")
                    identifier = args.get("session_id")
                    if identifier is not None and (not isinstance(identifier, str) or not SESSION_ID.fullmatch(identifier)):
                        raise ValueError("session_id must be a valid published session ID")
                    try:
                        if options.session_id_file:
                            published = published_session(options.session_id_file)
                            if identifier is not None and identifier != published:
                                raise SessionError("session_mismatch", "Supplied identity differs from the coordinator publication")
                            identifier = published
                        if not isinstance(identifier, str):
                            raise ValueError("session_id is required without a coordinator publication")
                        if (owner_id is not None and identifier != owner_id) or (reference and identifier != reference["id"]):
                            raise SessionError("session_mismatch", "This interpreter belongs to a different agent session; use a separate MCP server")
                        if bool(authority) != bool(claimant):
                            raise SessionError("claimant_required", "Supply both claimant arguments or neither")
                        owner_id = identifier
                        config.update(sessionId=identifier, claimantAuthority=authority or "agent-session",
                                      claimantId=claimant or identifier)
                        if current is None or name == "mc_reset" and current.closed:
                            if current:
                                current.close()
                            current = worker_factory(config)
                        result = current.request({"reset": True} if name == "mc_reset" else {"code": args["code"]})
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
