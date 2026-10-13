"""Private agent notes about difficult Machine Control use.

Notes are explicitly authored by an agent. Each carries a self-asserted agent
session reference so a later reviewer can open the transcript and correlate
the claim's retained audit commands. Nothing here is authentication.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import quote

import audit_history as audit

SCHEMA = "machine-control-usage-journal/v0"
MAX_NOTES = 10000
MAX_NOTE_BYTES = 4096
MAX_GOAL_CHARACTERS = 200
MAX_COMMANDS = 200
NOTE_KINDS = ("friction", "workaround", "fallback", "handoff", "follow-up", "summary")
TARGET = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


class JournalError(Exception):
    pass


def directory():
    override = os.environ.get("MACHINE_CONTROL_USAGE_DIR")
    if override:
        root = Path(override).expanduser()
    elif os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "MachineControl/usage"
    else:
        root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "machine-control/usage"
    if not root.is_absolute():
        raise JournalError("Usage journal directory must be absolute")
    return root


def connect(*, read=False):
    root = directory()
    path = root / "notes.sqlite3"
    if read and not path.exists():
        return None
    if not read:
        root.mkdir(parents=True, mode=0o700, exist_ok=True)
    audit.verify(root, folder=True)
    if not read:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
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
        db.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, kind TEXT NOT NULL, session TEXT, target TEXT, claim TEXT, data TEXT NOT NULL)")
        db.execute("CREATE INDEX IF NOT EXISTS notes_session ON notes(session)")
        db.commit()
    return db


def note(kind, text, *, goal=None, target=None, claim=None, session=None):
    if kind not in NOTE_KINDS:
        raise JournalError("Unknown usage note kind")
    if goal is not None:
        goal = goal.strip()
        if not goal or len(goal) > MAX_GOAL_CHARACTERS or any(c in goal for c in "\r\n\x00"):
            raise JournalError("Goal must be one nonempty line of at most 200 characters")
    if target is not None and not TARGET.fullmatch(target):
        raise JournalError("Invalid logical target alias")
    if claim is not None and not audit.CLAIM.fullmatch(claim):
        raise JournalError("Invalid claim ID")
    reference = audit.session_ref(session)
    if session is not None and reference is None:
        raise JournalError("Invalid session reference")
    value = dict(schema=SCHEMA, timestamp=audit.now(), source="agent", kind=kind,
                 goal=goal, text=text, logicalTarget=target, claimId=claim,
                 sessionRef=reference, agent=audit.agent_label())
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    if len(encoded.encode()) > audit.MAX_EVENT_BYTES:
        raise JournalError("Usage note exceeds its bound")
    db = connect()
    try:
        with db:
            cursor = db.execute(
                "INSERT INTO notes(timestamp,kind,session,target,claim,data) VALUES (?,?,?,?,?,?)",
                (value["timestamp"], kind, reference and reference["id"], target, claim, encoded))
            db.execute("DELETE FROM notes WHERE id <= (SELECT id FROM notes ORDER BY id DESC LIMIT 1 OFFSET ?)",
                       (MAX_NOTES,))
        return dict(value, noteId=cursor.lastrowid)
    finally:
        db.close()


def commands(note_value):
    """Retained audit commands for the note's claim, else its agent session."""
    selector = {}
    if note_value.get("claimId"):
        selector["claim"] = note_value["claimId"]
    elif note_value.get("sessionRef"):
        selector["session"] = note_value["sessionRef"]["id"]
    else:
        return None
    history = audit.history(limit=MAX_COMMANDS, **selector)
    projected = []
    for event in history["events"]:
        if event.get("event") != "command.result":
            continue
        projected.append({key: event[key] for key in (
            "timestamp", "logicalTarget", "command", "accepted", "delivery",
            "effect", "uncertainty", "errorCode", "exitCode", "elapsedMs")
            if key in event})
    return dict(selector=next(iter(selector)), commands=projected,
                truncated=history["nextBeforeId"] is not None,
                auditAvailable=history["available"])


def show(*, session=None, target=None, kind=None, since=None, before=None,
         limit=50, with_commands=False):
    db = connect(read=True)
    coverage = dict(complete=False, maximumNotes=MAX_NOTES,
                    auditRetentionDays=audit.RETENTION_DAYS,
                    limitations=["Only friction an agent chose to record",
                                 "Notes and session references are self-asserted",
                                 "Audit commands omit arguments and payloads; the transcript has detail",
                                 "Audit history expires before notes do",
                                 "Same-user editable; deletion can leave gaps"])
    if db is None:
        return dict(schema=SCHEMA, available=False, notes=[], nextBeforeId=None,
                    coverage=coverage)
    try:
        clauses, parameters = [], []
        for column, item in (("session", session), ("target", target), ("kind", kind)):
            if item:
                clauses.append(column + "=?")
                parameters.append(item)
        if since:
            clauses.append("timestamp>=?")
            parameters.append(since)
        if before:
            clauses.append("id<?")
            parameters.append(before)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = db.execute("SELECT id,data FROM notes" + where + " ORDER BY id DESC LIMIT ?",
                          [*parameters, limit + 1]).fetchall()
    finally:
        db.close()
    more = len(rows) > limit
    rows = rows[:limit]
    notes = []
    for identifier, data in reversed(rows):
        value = dict(json.loads(data), noteId=identifier)
        if with_commands:
            value["audit"] = commands(value)
        notes.append(value)
    return dict(schema=SCHEMA, available=True, notes=notes,
                nextBeforeId=rows[-1][0] if more else None, coverage=coverage)


def markdown(value):
    lines = ["# Machine Control usage notes", "",
             "Agent-authored and incomplete; open the referenced session transcript for detail.", ""]
    for item in value["notes"]:
        reference = item.get("sessionRef") or {}
        lines += [f"## {item['timestamp']} — {item['kind']}" +
                  (f": {item['goal']}" if item.get("goal") else ""), ""]
        lines += [f"- Session: {reference.get('id', 'unknown')} ({reference.get('source', 'none')})",
                  f"- Agent: {item.get('agent') or 'unknown'}",
                  f"- Target: {item.get('logicalTarget') or 'unspecified'}; claim: {item.get('claimId') or 'none'}",
                  "", item["text"], ""]
        trail = item.get("audit")
        if trail:
            lines += [f"Audit commands by {trail['selector']}" +
                      (" (newest page only)" if trail["truncated"] else "") + ":", ""]
            for command in trail["commands"]:
                outcome = "accepted" if command.get("accepted") else (
                    command.get("errorCode") or f"exit {command.get('exitCode')}")
                lines.append(f"- {command['timestamp']} `{command['command']}` → {outcome}")
            lines.append("")
    if value["nextBeforeId"]:
        lines += ["Older notes remain; next --before " + str(value["nextBeforeId"]), ""]
    return "\n".join(lines)


def handle(arguments, *, target=None, claim=None):
    parser = argparse.ArgumentParser(prog="machine-control usage")
    operations = parser.add_subparsers(dest="operation", required=True)
    write = operations.add_parser(
        "note", help="Read a non-secret agent note from stdin; global --target/--claim attach context")
    write.add_argument("--kind", choices=NOTE_KINDS, required=True)
    write.add_argument("--goal", help="One line: what you were trying to do")
    write.add_argument("--session-ref", help="Override the detected agent session ID")
    query = operations.add_parser("show")
    query.add_argument("--session-ref")
    query.add_argument("--kind", choices=NOTE_KINDS)
    query.add_argument("--since")
    query.add_argument("--before", type=int)
    query.add_argument("--limit", type=int, default=50)
    query.add_argument("--commands", action="store_true",
                       help="Attach retained audit commands for each note's claim or session")
    query.add_argument("--markdown", action="store_true")
    options = parser.parse_args(arguments)
    if options.operation == "note":
        # Validate context and storage before reading caller-authored input.
        note_context = dict(goal=options.goal, target=target, claim=claim,
                            session=options.session_ref)
        if claim is not None and not audit.CLAIM.fullmatch(claim):
            raise JournalError("Invalid claim ID")
        connect().close()
        text = sys.stdin.buffer.read(MAX_NOTE_BYTES + 1)
        if len(text) > MAX_NOTE_BYTES:
            raise JournalError("Usage note exceeds 4096 bytes")
        text = text.decode("utf-8").strip()
        if not text or "\x00" in text:
            raise JournalError("Usage note must be nonempty UTF-8 text")
        return note(options.kind, text, **note_context)
    if not 1 <= options.limit <= 500 or options.before is not None and options.before < 1:
        raise JournalError("Invalid usage page bounds")
    since = None
    if options.since:
        parsed = datetime.fromisoformat(options.since.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise JournalError("--since requires a timezone")
        since = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    value = show(session=options.session_ref, target=target, kind=options.kind,
                 since=since, before=options.before, limit=options.limit,
                 with_commands=options.commands)
    return markdown(value) if options.markdown else value
