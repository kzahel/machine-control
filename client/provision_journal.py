"""Dated, private provisioning evidence and explicitly authored agent notes.

No automatic event stores argv, stdin, environment, or raw provider output.
This is cooperative operational evidence, not authorization or authentication.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import time
from urllib.parse import quote

import audit_history as audit

SCHEMA = "machine-control-provision-journal/v0"
RUN = re.compile(r"p-\d{8}T\d{6}Z-[a-f0-9]{16}")
MAX_EVENTS = 10000
MAX_NOTE_BYTES = 4096
MAX_OUTPUT_BYTES = 256 * 1024
STAGE_SCHEMAS = {
    "winvm-factory-stages/v0", "linuxvm-factory-stages/v0",
    "macvm-bootstrap-stages/v0",
}
STATES = {"complete", "action_required", "waiting", "human_required",
          "unverified", "blocked"}
# Owned inspector vocabulary only. Unknown/new names are reported as omitted.
STAGES = set("host media image-index vm target-config identity first-logon "
             "cloud-init transport credential credential-handoff bootstrap "
             "resident maintenance promotion power guest-agent desktop capture "
             "boot-media create destination prepared-media seed-inputs seed-media "
             "source-media cloud-attestation cloud-image final-stop accessibility "
             "administrator-authorization doctor guest-tools host-consent "
             "outer-bootstrap".split())
NOTE_KINDS = ("friction", "workaround", "fix", "follow-up", "summary")


class JournalError(Exception):
    pass


def directory():
    override = os.environ.get("MACHINE_CONTROL_PROVISION_DIR")
    if override:
        root = Path(override).expanduser()
    elif os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "MachineControl/provisioning"
    else:
        root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "machine-control/provisioning"
    if not root.is_absolute():
        raise JournalError("Provisioning directory must be absolute")
    return root


def connect(identifier, *, create=False, read=False):
    if not isinstance(identifier, str) or not RUN.fullmatch(identifier):
        raise JournalError("Invalid provisioning run ID")
    root = directory()
    if create:
        root.mkdir(parents=True, mode=0o700, exist_ok=True)
    audit.verify(root, folder=True)
    path = root / (identifier + ".sqlite3")
    if create:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    audit.verify(path)
    for suffix in ("-journal", "-wal", "-shm"):
        try:
            audit.verify(Path(str(path) + suffix), transient=True)
        except FileNotFoundError:
            pass
    db = sqlite3.connect("file:" + quote(path.as_posix(), safe="/:") +
                         ("?mode=ro" if read else "?mode=rw"), uri=True, timeout=5)
    if not read:
        db.execute("PRAGMA synchronous=FULL")
    if create:
        db.execute("CREATE TABLE run (data TEXT NOT NULL)")
        db.execute("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, kind TEXT NOT NULL, correlation TEXT, data TEXT NOT NULL)")
        db.execute("CREATE INDEX events_correlation ON events(kind,correlation)")
        db.commit()
    return db


def insert(db, kind, fields, *, source="automatic"):
    if db.execute("SELECT COUNT(*) FROM events").fetchone()[0] >= MAX_EVENTS:
        raise JournalError("Provisioning journal event limit reached")
    value = dict(schema=SCHEMA, timestamp=audit.now(), source=source,
                 event=kind, **fields)
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    if len(encoded.encode()) > audit.MAX_EVENT_BYTES:
        raise JournalError("Provisioning event exceeds its bound")
    db.execute("INSERT INTO events(timestamp,kind,correlation,data) VALUES (?,?,?,?)",
               (value["timestamp"], kind, fields.get("correlationId"), encoded))
    return value


def append(identifier, kind, fields, *, source="automatic", require_open=False):
    db = connect(identifier)
    try:
        with db:
            # Serialize finish against new command intents and concurrent notes.
            db.execute("BEGIN IMMEDIATE")
            run = json.loads(db.execute("SELECT data FROM run").fetchone()[0])
            if require_open and run["outcome"] != "in_progress":
                raise JournalError("Provisioning run is finished; begin a new run")
            return insert(db, kind, fields, source=source)
    finally:
        db.close()


def begin(platform, profile):
    identifier = "p-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(8)
    run = dict(schema=SCHEMA, runId=identifier, startedAt=audit.now(),
               platform=platform, profile=profile, outcome="in_progress",
               finishedAt=None, outcomeSource="agent")
    db = connect(identifier, create=True)
    try:
        with db:
            db.execute("INSERT INTO run VALUES (?)", (json.dumps(run),))
            insert(db, "run.started", {"platform": platform, "profile": profile})
    finally:
        db.close()
    return {**run, "journalPath": str(directory() / (identifier + ".sqlite3"))}


def finish(identifier, outcome):
    db = connect(identifier)
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            run = json.loads(db.execute("SELECT data FROM run").fetchone()[0])
            if run["outcome"] != "in_progress":
                raise JournalError("Provisioning run is already finished")
            run.update(outcome=outcome, finishedAt=audit.now())
            # Unpaired intents remain unknown, including killed controllers.
            unknown = pending(db)
            if outcome == "ready" and unknown:
                raise JournalError("Cannot report ready with unpaired command intents")
            insert(db, "run.finished", {"outcome": outcome,
                    "unpairedCommands": unknown}, source="agent")
            db.execute("UPDATE run SET data=?", (json.dumps(run),))
        return {**run, "unpairedCommands": unknown}
    finally:
        db.close()


def pending(db):
    return db.execute("SELECT COUNT(*) FROM events i WHERE i.kind='command.intent' AND NOT EXISTS (SELECT 1 FROM events r WHERE r.kind='command.result' AND r.correlation=i.correlation)").fetchone()[0]


def show(identifier, *, before=None, limit=100):
    db = connect(identifier, read=True)
    try:
        run = json.loads(db.execute("SELECT data FROM run").fetchone()[0])
        where, parameters = (" WHERE id<?", [before]) if before else ("", [])
        rows = db.execute("SELECT id,data FROM events" + where + " ORDER BY id DESC LIMIT ?",
                          [*parameters, limit + 1]).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        return dict(schema=SCHEMA, run=run,
                    events=[dict(json.loads(data), eventId=i) for i, data in reversed(rows)],
                    nextBeforeId=rows[-1][0] if more else None,
                    coverage=dict(complete=False, unpairedCommands=pending(db),
                        maximumEvents=MAX_EVENTS, automaticRetention=False,
                        rawOutputRecorded=False, argumentsRecorded=False,
                        limitations=["Only common CLI calls attached to this run",
                                     "Direct platform scripts and guest logs are separate evidence",
                                     "Agent notes/outcome are self-reported, not acceptance proof",
                                     "Missing results have unknown outcome",
                                     "Same-user editable; storage failure or deletion can leave gaps"]))
    finally:
        db.close()


def stage_projection(value):
    if not isinstance(value, dict) or not isinstance(value.get("schema"), str) or value["schema"] not in STAGE_SCHEMAS:
        return None
    stages = value.get("stages")
    if not isinstance(stages, list) or len(stages) > 100:
        return None
    projected = []
    for item in stages:
        if not isinstance(item, dict):
            continue
        if (isinstance(item.get("name"), str) and item["name"] in STAGES
                and isinstance(item.get("state"), str) and item["state"] in STATES):
            projected.append({"name": item["name"], "state": item["state"]})
    return dict(inspectorSchema=value["schema"], stages=projected,
                omittedStages=len(stages) - len(projected))


class Command:
    def __init__(self, identifier, arguments, claim_id=None):
        self.identifier = identifier
        self.started = time.monotonic()
        self.finished = False
        self.result = {}
        command, omitted = audit.command_description(arguments)
        self.fields = dict(correlationId=secrets.token_hex(16), command=command,
                           argumentCountOmitted=omitted, logicalTarget=None,
                           claimId=claim_id if isinstance(claim_id, str) and audit.CLAIM.fullmatch(claim_id) else None,
                           payloadsRecorded=False)
        append(identifier, "command.intent", self.fields, require_open=True)

    def bind(self, command):
        self.fields.update(auditCorrelationId=command.fields["correlationId"],
                           logicalTarget=command.fields["logicalTarget"],
                           platform=command.fields["platform"],
                           claimId=command.fields["claimId"])

    def observe(self, value):
        audit.Command.observe(self, value)

    def stages(self, output):
        try:
            projected = stage_projection(json.loads(output))
        except (ValueError, UnicodeDecodeError):
            projected = None
        self.result["stageObservation"] = projected or {"available": False}

    def finish(self, exit_code=None, error_code=None):
        self.finished = True
        fields = dict(self.fields, **self.result, exitCode=exit_code,
                      elapsedMs=int((time.monotonic() - self.started) * 1000))
        if error_code:
            fields["errorCode"] = error_code
        try:
            return append(self.identifier, "command.result", fields)
        except (JournalError, audit.AuditError, OSError, sqlite3.Error, ValueError):
            print("machine-control: provisioning persistence unavailable; coverage gap; do not replay an uncertain operation", file=sys.stderr)
            return None


def markdown(value):
    run = value["run"]
    lines = ["# Provisioning journal " + run["runId"], "",
             f"Started: {run['startedAt']}; {run['platform']}/{run['profile']}",
             "Outcome (agent reported): " + run["outcome"], "",
             "Coverage is incomplete. Unpaired commands: " + str(value["coverage"]["unpairedCommands"]), ""]
    for event in value["events"]:
        lines += [f"## {event['timestamp']} — {event['event']} ({event['source']})", ""]
        if event["event"] == "agent.note":
            lines += [event["kind"] + ":", "", event["text"], ""]
        else:
            lines += ["```json", json.dumps(event, sort_keys=True, indent=2), "```", ""]
    if value["nextBeforeId"]:
        lines += ["Older events remain; next --before " + str(value["nextBeforeId"]), ""]
    return "\n".join(lines)


def handle(arguments):
    parser = argparse.ArgumentParser(prog="machine-control provision")
    commands = parser.add_subparsers(dest="operation", required=True)
    start = commands.add_parser("begin")
    start.add_argument("--platform", choices=("windows", "linux", "macos"), required=True)
    start.add_argument("--profile", choices=("runtime", "development"), default="development")
    note = commands.add_parser("note", help="Read a non-secret agent note from stdin")
    note.add_argument("run")
    note.add_argument("--kind", choices=NOTE_KINDS, required=True)
    end = commands.add_parser("finish")
    end.add_argument("run")
    end.add_argument("--outcome", choices=("ready", "blocked", "failed", "abandoned"), required=True)
    query = commands.add_parser("show")
    query.add_argument("run")
    query.add_argument("--before", type=int)
    query.add_argument("--limit", type=int, default=100)
    query.add_argument("--markdown", action="store_true")
    options = parser.parse_args(arguments)
    if options.operation == "begin":
        return begin(options.platform, options.profile)
    if options.operation == "finish":
        return finish(options.run, options.outcome)
    if options.operation == "note":
        # Validate storage before reading even non-secret caller-authored input.
        db = connect(options.run, read=True)
        db.close()
        text = sys.stdin.buffer.read(MAX_NOTE_BYTES + 1)
        if len(text) > MAX_NOTE_BYTES:
            raise JournalError("Agent note exceeds 4096 bytes")
        text = text.decode("utf-8").strip()
        if not text or "\x00" in text:
            raise JournalError("Agent note must be nonempty UTF-8 text")
        return append(options.run, "agent.note", dict(kind=options.kind, text=text), source="agent")
    if not 1 <= options.limit <= 500 or options.before is not None and options.before < 1:
        raise JournalError("Invalid journal page bounds")
    value = show(options.run, before=options.before, limit=options.limit)
    return markdown(value) if options.markdown else value
