"""Private controller history for cooperative claims and common CLI use.

This is an operational journal, not authentication or a same-user security
boundary. Never retain argv, payloads, stdin, environment or provider output.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import sys
import time
from urllib.parse import quote

SCHEMA = "machine-control-audit/v0"
MAX_EVENTS = 50000
RETENTION_DAYS = 30
MAX_EVENT_BYTES = 16384
CLAIM = re.compile(r"c-[a-f0-9]{24}")
VERBS = frozenset(
    "status capabilities doctor up down suspend shutdown force-stop reboot ensure-ready validate-candidate prepare-promotion acquire renew release check inventory gc snapshot action capture input applications windows launch activate close artifact read observe request approve deny revoke open poll accept cancel heartbeat exec ps ssh wsl ui login credential store rotate verify establish deploy deploy-ui deploy-fixture factory stage factory-stages bootstrap-stages preflight factory-create factory-status factory-preflight factory-media-status factory-detach-installer factory-detach-media post-update audit repair certify seal delete repair-registration target-id pin-target trust-ssh-host-key host-doctor bootstrap setup run enable disable identity instructions list guide credentials control session stream type key click drag scan move scroll press permissions find get inspect analyze".split()
)
OPERATIONS = frozenset(
    "claim target workspace maintenance desktop control grant update browser ios testbed os run inventory storage agent audit".split()
)


class AuditError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def directory():
    override = os.environ.get("MACHINE_CONTROL_AUDIT_DIR")
    if override:
        path = Path(override).expanduser()
    elif os.name == "nt":
        path = (
            Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
            / "MachineControl/audit"
        )
    else:
        path = (
            Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
            / "machine-control/audit"
        )
    if not path.is_absolute():
        raise AuditError("Audit directory must be absolute")
    return path


def verify(path, *, folder=False, transient=False):
    info = path.lstat()
    expected = stat.S_ISDIR if folder else stat.S_ISREG
    if (
        not expected(info.st_mode)
        or not folder
        and (info.st_nlink > 1 or info.st_nlink == 0 and not transient)
    ):
        raise AuditError("Unsafe audit storage")
    if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise AuditError("Audit storage is not private")


def connect(*, read=False):
    root = directory()
    if read and not root.exists():
        return None
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    verify(root, folder=True)
    path = root / "history.sqlite3"
    if read and not path.exists():
        return None
    if not read:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
    verify(path)
    for suffix in ("-journal", "-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        try:
            # SQLite removes rollback journals on commit. A concurrent stat
            # may see an already-unlinked regular inode or no entry at all.
            verify(sidecar, transient=True)
        except FileNotFoundError:
            pass
    db = sqlite3.connect(
        "file:"
        + quote(path.as_posix(), safe="/:")
        + ("?mode=ro" if read else "?mode=rw"),
        uri=True,
        timeout=1,
    )
    if not read:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA auto_vacuum=FULL")
        db.execute(
            "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, target TEXT, claim TEXT, resource TEXT, claimant TEXT, data TEXT NOT NULL)"
        )
        db.execute("CREATE INDEX IF NOT EXISTS events_claim ON events(claim)")
        db.execute("CREATE INDEX IF NOT EXISTS events_target ON events(target)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        db.execute("INSERT OR IGNORE INTO metadata VALUES ('startedAt', ?)", (now(),))
        db.commit()
    return db


def append(event, **fields):
    value = dict(
        schema=SCHEMA, event=event, timestamp=now(), callerPid=os.getpid(), **fields
    )
    encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=True)
    if len(encoded.encode()) > MAX_EVENT_BYTES:
        raise AuditError("Audit event exceeds its bound")
    db = connect()
    try:
        with db:
            db.execute(
                "INSERT INTO events(timestamp,target,claim,resource,claimant,data) VALUES (?,?,?,?,?,?)",
                (
                    value["timestamp"],
                    fields.get("logicalTarget"),
                    fields.get("claimId"),
                    fields.get("resourceKey"),
                    fields.get("claimant", {}).get("id"),
                    encoded,
                ),
            )
            cutoff = (
                (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS))
                .isoformat()
                .replace("+00:00", "Z")
            )
            db.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))
            db.execute(
                "DELETE FROM events WHERE id <= (SELECT id FROM events ORDER BY id DESC LIMIT 1 OFFSET ?)",
                (MAX_EVENTS,),
            )
    finally:
        db.close()
    return value


def best_effort(event, **fields):
    try:
        return append(event, **fields)
    except (AuditError, OSError, sqlite3.Error, ValueError):
        print(
            "machine-control: audit persistence unavailable; history has a coverage gap",
            file=sys.stderr,
        )
        return None


def claim_transition(previous, current, resource_key, *, reason=None, observed_at=None):
    old = (previous or {}).get("active")
    new = current.get("active")
    base = dict(
        resourceKey=resource_key,
        provider=current["resource"]["provider"],
        logicalTarget=os.environ.get("MACHINE_CONTROL_AUDIT_TARGET"),
    )

    def record(event, claim, **extra):
        best_effort(
            event,
            **base,
            claimId=claim["claimId"],
            generation=claim["generation"],
            claimant=claim["claimant"],
            reason=claim["reason"],
            useClass=claim.get("useClass", "ordinary"),
            acquiredAt=claim["acquiredAt"],
            expiresAt=claim["expiresAt"],
            **extra,
        )

    if old and (not new or old["claimId"] != new["claimId"]):
        expired = old["expiresAt"] <= (observed_at or now())
        record(
            "claim.expired" if expired else "claim.released",
            old,
            endReason=reason or ("expiry_observed" if expired else "release"),
        )
    if new and (not old or old["claimId"] != new["claimId"]):
        record("claim.acquired", new)
    elif new and old and new["renewedAt"] != old["renewedAt"]:
        record("claim.renewed", new)


def command_description(arguments):
    # Preserve only known grammar tokens before an opaque argument. A token
    # resembling a verb inside arbitrary shell/code arguments is never logged.
    if not arguments or arguments[0] not in OPERATIONS:
        return "opaque", len(arguments)
    parts = [arguments[0]]
    for token in arguments[1:]:
        if token == "--":
            continue
        if token not in VERBS:
            break
        parts.append(token)
        if token in {
            "exec",
            "ps",
            "ssh",
            "wsl",
            "run",
            "input",
            "action",
            "type",
            "key",
            "click",
            "drag",
            "scan",
        }:
            break
        if len(parts) == 4:
            break
    return " ".join(parts), len(arguments) - len(parts)


def program_kind(arguments):
    values = list(arguments[1:])
    operation = arguments[0] if arguments else None
    if operation == "run":
        if "--" not in values:
            return None
        values = values[values.index("--") + 1 :]
    elif operation in {"testbed", "os"}:
        if values and values[0] == "--":
            values.pop(0)
        if operation == "testbed":
            if not values or values.pop(0) != "exec":
                return None
        while values and values[0] in {"-i", "-t", "--"}:
            values.pop(0)
    else:
        return None
    executable = re.split(r"[/\\]", values[0])[-1].lower() if values else ""
    return {
        "python": "python",
        "python3": "python",
        "python.exe": "python",
        "node": "javascript",
        "bun": "javascript",
        "bash": "shell",
        "sh": "shell",
        "zsh": "shell",
        "pwsh": "powershell",
        "powershell.exe": "powershell",
        "macui": "native_control",
        "sudo": "administrator",
        "systemctl": "service_management",
        "launchctl": "service_management",
        "dotnet": "dotnet",
    }.get(executable)


class Command:
    def __init__(self, target, platform, arguments, claim_id=None):
        self.started = time.monotonic()
        self.finished = False
        self.result = {}
        command, omitted = command_description(arguments)
        self.fields = dict(
            correlationId=secrets.token_hex(16),
            logicalTarget=target,
            platform=platform,
            command=command,
            argumentCountOmitted=omitted,
            payloadsRecorded=False,
            programKind=program_kind(arguments),
            claimId=claim_id,
        )
        append("command.intent", **self.fields)

    def observe(self, value):
        if not isinstance(value, dict):
            return
        for key in ("accepted", "delivery", "effect", "uncertainty", "errorCode"):
            field = value.get(key)
            if (
                type(field) is bool
                or field is None
                or isinstance(field, str)
                and len(field) <= 128
                and re.fullmatch(r"[a-zA-Z0-9_.-]+", field)
            ):
                if key in value:
                    self.result[key] = field
        # Never adopt another holder from a refused acquire/status response.
        if value.get("accepted") is True and value.get("operation") == "acquire":
            claim = value.get("data", {}).get("claim", {})
            identifier = claim.get("claimId")
            if isinstance(identifier, str) and CLAIM.fullmatch(identifier):
                self.fields["claimId"] = identifier

    def finish(self, exit_code=None, error_code=None):
        self.finished = True
        fields = dict(
            self.fields,
            **self.result,
            exitCode=exit_code,
            elapsedMs=int((time.monotonic() - self.started) * 1000),
        )
        if error_code:
            fields["errorCode"] = error_code
        return best_effort("command.result", **fields)


def history(
    *, target=None, claim=None, claimant=None, since=None, before=None, limit=100
):
    db = connect(read=True)
    if db is None:
        return dict(
            schema=SCHEMA,
            available=False,
            events=[],
            coverage={"startedAt": None, "earliestRetainedAt": None, "complete": False},
            nextBeforeId=None,
        )
    try:
        clauses, parameters = [], []
        if target:
            clauses.append(
                "(target=? OR claim IN (SELECT claim FROM events WHERE target=? AND claim IS NOT NULL))"
            )
            parameters += [target, target]
        if claim:
            clauses.append("claim=?")
            parameters.append(claim)
        if claimant:
            clauses.append("claim IN (SELECT claim FROM events WHERE claimant=?)")
            parameters.append(claimant)
        if since:
            clauses.append("timestamp>=?")
            parameters.append(since)
        if before:
            clauses.append("id<?")
            parameters.append(before)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = db.execute(
            "SELECT id,data FROM events" + where + " ORDER BY id DESC LIMIT ?",
            [*parameters, limit + 1],
        ).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        events = []
        for identifier, data in reversed(rows):
            value = json.loads(data)
            value["eventId"] = identifier
            if value.get("claimId") and "claimant" not in value:
                binding = db.execute(
                    "SELECT data FROM events WHERE claim=? AND resource IS NOT NULL ORDER BY id DESC LIMIT 1",
                    (value["claimId"],),
                ).fetchone()
                if binding:
                    source = json.loads(binding[0])
                    for key in ("resourceKey", "provider", "claimant", "generation"):
                        value[key] = source[key]
            events.append(value)
        earliest = db.execute("SELECT MIN(timestamp) FROM events").fetchone()[0]
        started = db.execute(
            "SELECT value FROM metadata WHERE key='startedAt'"
        ).fetchone()[0]
        return dict(
            schema=SCHEMA,
            available=True,
            events=events,
            coverage=dict(
                startedAt=started,
                earliestRetainedAt=earliest,
                complete=False,
                maximumEvents=MAX_EVENTS,
                retentionDays=RETENTION_DAYS,
                limitations=[
                    "No retrospective reconstruction",
                    "Raw provider/shell bypasses are not captured",
                    "Same-user editable; attribution is self-asserted",
                    "Missing results have unknown outcome",
                    "Retention or unavailable writes can remove history",
                ],
            ),
            nextBeforeId=rows[-1][0] if more else None,
        )
    finally:
        db.close()


def handle(arguments, *, target=None):
    parser = argparse.ArgumentParser(prog="machine-control audit history")
    parser.add_argument("--claim-id")
    parser.add_argument("--claimant-id")
    parser.add_argument("--since")
    parser.add_argument("--before", type=int)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--json", action="store_true")
    if not arguments or arguments[0] != "history":
        raise AuditError(
            "Use audit history [--claim-id ID] [--claimant-id ID] [--since UTC] [--limit 1..500]"
        )
    options = parser.parse_args(arguments[1:])
    if (
        not 1 <= options.limit <= 500
        or options.before is not None
        and options.before < 1
    ):
        raise AuditError("Invalid audit page bounds")
    if options.claim_id and not CLAIM.fullmatch(options.claim_id):
        raise AuditError("Invalid audit claim selector")
    since = None
    if options.since:
        parsed = datetime.fromisoformat(options.since.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise AuditError("Audit --since requires a timezone")
        since = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return history(
        target=target,
        claim=options.claim_id,
        claimant=options.claimant_id,
        since=since,
        before=options.before,
        limit=options.limit,
    )
