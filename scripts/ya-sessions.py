#!/usr/bin/env python3
"""Bounded YA REST session lifecycle helper (Python standard library only)."""
import argparse
import base64
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

MODEL = "gpt-6.1-sol"


class Error(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward authentication to a redirected endpoint.


def private_json(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
            raise Error("Private JSON file must be a regular mode-0600 file")
        return json.load(stream)


def save(path, value, exclusive=False):
    path = Path(path)
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
        return
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".ya-receipt-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Client:
    def __init__(self, base_url, headers=None):
        parsed = urllib.parse.urlsplit(base_url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise Error("Supply an explicit HTTP(S) base URL without credentials/query/fragment")
        self.base = base_url.rstrip("/")
        self.headers = {}
        for key, value in (headers or {}).items():
            if key.lower() not in ("authorization", "cookie") or not isinstance(value, str):
                raise Error("Auth JSON supports only Authorization and Cookie string headers")
            if "\r" in value or "\n" in value:
                raise Error("Invalid authentication header")
            self.headers[key] = value
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, route, body=None, missing=False):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + "/api" + route, data=data,
                                     method=method, headers={**self.headers,
                                                            "Content-Type": "application/json",
                                                            "X-Yep-Anywhere": "true"})
        try:
            with self.opener.open(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if missing and exc.code == 404:
                return None
            # Server error text may contain prompts, credentials or private routes.
            raise Error(f"YA HTTP {exc.code}; inspect privately; do not blindly retry mutations") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise Error("YA transport failed; mutation outcome may be unknown; do not blindly retry") from None
        except (ValueError, UnicodeError):
            raise Error("Invalid YA JSON response; mutation outcome may be unknown") from None


def segment(value):
    return urllib.parse.quote(value, safe="")


def project_id(path):
    # Encode the target-side path verbatim; never resolve it on the controller.
    if not (path.startswith("/") or (len(path) > 2 and path[1] == ":") or path.startswith("\\\\")):
        raise Error("Project path must be absolute on the YA execution host")
    return base64.urlsafe_b64encode(path.encode()).decode().rstrip("=")


def settings(client, effort, speed):
    provider = client.request("GET", "/providers/codex")["provider"]
    models = [m for m in provider.get("models", []) if m.get("id") == MODEL]
    if len(models) != 1:
        raise Error("Required model absent or ambiguous in Codex catalog")
    model = models[0]
    efforts = [e.get("reasoningEffort") for e in model.get("supportedReasoningEfforts", [])]
    if effort not in efforts:
        raise Error("Requested effort is not advertised for required model")
    tiers = [t.get("id") for t in model.get("serviceTiers", [])
             if str(t.get("name", "")).lower() == "fast"]
    if speed == "fast" and (len(tiers) != 1 or not tiers[0]):
        raise Error("Fast service tier absent or ambiguous for required model")
    return {"provider": "codex", "model": MODEL, "thinking": effort,
            "serviceTier": tiers[0] if speed == "fast" else "default"}


def accept(receipt, response):
    for key in ("processId", "sessionId", "queueId", "position"):
        if key in response:
            receipt[key] = response[key]
    receipt["outcome"] = "queued" if response.get("queued") else "accepted"
    receipt["queuePending"] = bool(response.get("queueId"))


def status(client, receipt):
    process = None
    queue_departed = False
    if receipt.get("queuePending"):
        queued = client.request("GET", "/queue/" + segment(receipt["queueId"]), missing=True)
        if queued:
            receipt.update(outcome="queued", position=queued.get("position"))
            receipt.pop("observation", None)
            return receipt
        queue_departed = True
    if receipt.get("sessionId"):
        result = client.request("GET", "/sessions/" + segment(receipt["sessionId"]) + "/process")
        process = result.get("process")
    if not process and receipt.get("processId"):
        # No single-process GET exists. Filter in memory; never emit the catalog.
        rows = client.request("GET", "/processes?includeTerminated=true")
        matches = [p for p in rows.get("processes", []) + rows.get("terminatedProcesses", [])
                   if p.get("id") == receipt["processId"]]
        if len(matches) > 1:
            raise Error("Ambiguous process identity")
        process = matches[0] if matches else None
    if queue_departed and process and process.get("state") == "terminated":
        process = None
    if process:
        receipt["queuePending"] = False
        if process.get("projectId") != receipt["projectId"] or process.get("provider") != "codex":
            raise Error("Process project/provider does not match receipt")
        if receipt.get("processId") and process.get("id") != receipt["processId"]:
            # A known canonical session can legitimately acquire a new process.
            receipt["previousProcessId"] = receipt["processId"]
        old = receipt.get("sessionId")
        current = process["sessionId"]
        if old and old != current:
            receipt.setdefault("previousSessionIds", []).append(old)
        receipt.update(sessionId=current, processId=process["id"], outcome="observed")
        selected = {"model": process.get("requestedModel"), "effort": process.get("effort"),
                    "serviceTier": process.get("serviceTier") or "default"}
        observation = {"state": process.get("state"), "queueDepth": process.get("queueDepth"),
                       "selected": selected,
                       "reportedModel": process.get("model"),
                       "providerServiceTier": process.get("serviceTier") or "default"}
        # Process.effort may be queued for the next turn. Do not call it applied.
        meta = client.request("GET", f'/projects/{receipt["projectId"]}/sessions/{segment(current)}/metadata')
        effective = meta.get("session", {}).get("effectiveLaunchSettings") or {}
        observation["lastApplied"] = {k: effective.get(k) for k in
                                      ("revision", "requestedModel", "effort", "serviceTier")}
        requested = receipt["requested"]
        observation["selectionMatchesRequest"] = (
            selected == {"model": requested["model"], "effort": requested["thinking"],
                         "serviceTier": requested["serviceTier"]})
        observation["appliedMatchesRequest"] = bool(effective) and (
            effective.get("requestedModel") == requested["model"]
            and effective.get("effort") == requested["thinking"]
            and (effective.get("serviceTier") or "default") == requested["serviceTier"])
        receipt["observation"] = observation
    elif receipt.get("queueId"):
        queued = None if queue_departed else client.request("GET", "/queue/" + segment(receipt["queueId"]), missing=True)
        receipt["outcome"] = "queued" if queued else "queue-departed-unresolved"
        if queued:
            receipt["position"] = queued.get("position")
        receipt.pop("observation", None)
    else:
        receipt["outcome"] = ("dispatch-outcome-unknown" if receipt.get("outcome") in
                              ("dispatch-pending", "dispatch-outcome-unknown", "abort-pending")
                              else "no-process-observed")
        receipt.pop("observation", None)
    return receipt


def run(args):
    receipt_path = Path(args.receipt).expanduser().absolute()
    root = Path(__file__).resolve().parent.parent
    if receipt_path.resolve().is_relative_to(root):
        raise Error("Receipt must be outside the public checkout")
    client = Client(args.base_url, private_json(args.auth_headers_file) if args.auth_headers_file else {})
    pid = project_id(args.project_path)
    message = None
    if args.command in ("create", "resume", "message"):
        message = sys.stdin.read() if args.message_file == "-" else Path(args.message_file).read_text()
        if not message.strip():
            raise Error("Message must not be empty")
    if args.command == "create":
        chosen = settings(client, args.effort, args.speed)
        receipt = {"baseUrl": client.base, "projectId": pid,
                   "requested": chosen, "outcome": "dispatch-pending"}
        # Reserve before dispatch. Existing receipt refuses accidental duplicate launch.
        save(receipt_path, receipt, exclusive=True)
    else:
        receipt = private_json(receipt_path)
        if receipt.get("baseUrl") != client.base or receipt.get("projectId") != pid:
            raise Error("Receipt endpoint/project mismatch")
    if args.command in ("create", "resume", "message"):
        requested = receipt["requested"]
        if (set(requested) != {"provider", "model", "thinking", "serviceTier"}
                or requested["provider"] != "codex" or requested["model"] != MODEL
                or requested["thinking"] not in ("low", "medium", "high")):
            raise Error("Receipt launch settings exceed this helper's bounded contract")
        if args.command != "create":
            status(client, receipt)
            if receipt.get("queuePending"):
                raise Error("Launch queue is pending or unresolved; no duplicate turn sent")
            if not receipt.get("sessionId"):
                raise Error("Canonical session unresolved; no message sent")
        if args.command == "create":
            route = f"/projects/{pid}/sessions"
        elif args.command == "resume":
            if receipt.get("observation", {}).get("state") not in (None, "terminated"):
                raise Error("Session has a live process; use message")
            route = f'/projects/{pid}/sessions/{segment(receipt["sessionId"])}/resume'
        else:
            if receipt.get("observation", {}).get("state") in (None, "terminated"):
                raise Error("No live process; use resume")
            route = f'/sessions/{segment(receipt["sessionId"])}/messages'
        receipt["outcome"] = "dispatch-pending"
        save(receipt_path, receipt)
        response = client.request("POST", route, {**receipt["requested"], "message": message})
        accept(receipt, response)
        save(receipt_path, receipt)
        status(client, receipt)
    elif args.command == "status":
        status(client, receipt)
    elif args.command == "abort":
        status(client, receipt)
        if receipt.get("outcome") == "queued":
            receipt["outcome"] = "queue-cancel-pending"
            save(receipt_path, receipt)
            result = client.request("DELETE", "/queue/" + segment(receipt["queueId"]))
            receipt["outcome"] = "queue-cancelled" if result.get("cancelled") else "cancel-unverified"
        elif receipt.get("observation", {}).get("state") not in (None, "terminated"):
            receipt["outcome"] = "abort-pending"
            save(receipt_path, receipt)
            result = client.request("POST", "/processes/" + segment(receipt["processId"]) + "/abort",
                                    {"blockResume": True})
            receipt["outcome"] = "stopped" if result.get("verifiedStopped") is True else "stop-unverified"
            exemption = result.get("resumeExemption", {})
            receipt["resumeExemption"] = {k: exemption.get(k) for k in
                                          ("heartbeatDisabled", "autoResumeDisabled")}
        else:
            raise Error("No live process resolved; nothing aborted")
    save(receipt_path, receipt)
    # Only lifecycle/configuration evidence: no auth, messages, titles, or catalog.
    return {k: receipt[k] for k in ("outcome", "sessionId", "processId", "queueId", "position",
                                   "observation", "resumeExemption") if k in receipt}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="YA server root (without /api)")
    parser.add_argument("--project-path", required=True, help="Exact absolute path on execution host")
    parser.add_argument("--receipt", required=True, help="Private file outside public checkout")
    parser.add_argument("--auth-headers-file", help="Existing mode-0600 JSON Authorization/Cookie headers")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("create", "status", "message", "resume", "abort"):
        child = sub.add_parser(command)
        if command in ("create", "message", "resume"):
            child.add_argument("--message-file", required=True, help="Prompt file, or - for stdin")
        if command == "create":
            child.add_argument("--effort", choices=("low", "medium", "high"), default="low")
            child.add_argument("--speed", choices=("normal", "fast"), default="normal")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args), indent=2))
    except Error as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        # Avoid leaking file contents/paths or server-supplied values in exceptions.
        print("YA operation failed; inspect private receipt and server state before retrying.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
