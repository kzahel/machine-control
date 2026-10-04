"""Connection-owned waiting for an exact adapter-selected target.

The existing same-user claim store is the single transaction authority. Labels
remain self-asserted coordination, not authenticated caller authority. All file
operations below run under its operation lock. No queued owner is restored into
a replacement connection, and keepalives never renew the underlying claim.
"""
from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import time

import claims

SCHEMA = "machine-control-claim-admission/v1"
FILE_SCHEMA = "machine-control-claim-queue-record/v1"
WAIT_LEASE = 60
OFFER_LEASE = 15
ACTIVE_LEASE = 5
MAX_ENTRIES = 256


def load(directory):
    path = directory / "queue.json"
    if not path.exists():
        return {"schema": FILE_SCHEMA, "revision": 0, "sequence": 0, "entries": []}
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 2 * 1024 * 1024 \
            or os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise claims.ClaimError("claim_queue_invalid", "Claim queue is not private")
    try:
        value = json.loads(path.read_text())
        assert set(value) == {"schema", "revision", "sequence", "entries"}
        assert value["schema"] == FILE_SCHEMA
        assert all(type(value[k]) is int and value[k] >= 0 for k in ("revision", "sequence"))
        assert isinstance(value["entries"], list) and len(value["entries"]) <= MAX_ENTRIES
        owners = set()
        for item in value["entries"]:
            assert set(item) == {"owner", "pid", "resource", "sequence", "deadline", "heartbeat",
                                 "offerDeadline", "offerGeneration", "state", "claimId", "terminalReason"}
            assert isinstance(item["owner"], str) and re.fullmatch(r"[a-f0-9]{32}", item["owner"]) and item["owner"] not in owners
            owners.add(item["owner"])
            assert isinstance(item["resource"], str) and re.fullmatch(r"[a-f0-9]{64}", item["resource"])
            assert item["state"] in {"waiting_for_resource", "offered", "activating", "active", "ended"}
            assert all(type(item[k]) is int and item[k] >= 0 for k in ("pid", "sequence", "offerGeneration"))
            assert all(type(item[k]) in (float, int) and math.isfinite(item[k]) and item[k] >= 0
                       for k in ("deadline", "heartbeat", "offerDeadline"))
            assert item["claimId"] is None or claims.CLAIM_PATTERN.fullmatch(item["claimId"])
            assert item["terminalReason"] is None or isinstance(item["terminalReason"], str)
        return value
    except (ValueError, TypeError, KeyError, AssertionError) as error:
        raise claims.ClaimError("claim_queue_invalid", "Claim queue state is invalid") from error


def save(directory, value):
    claims.write_record(directory / "queue.json", value)


def record_for_digest(directory, digest):
    path = directory / f"resource-{digest}.json"
    if not path.exists():
        return path, None
    if path.is_symlink() or not path.is_file():
        raise claims.ClaimError("claim_state_invalid", "Claim record entry is unsafe")
    try:
        value = json.loads(path.read_text())
        provider, identity = value["resource"]["provider"], value["resource"]["id"]
        if claims.resource_digest(provider, identity) != digest:
            raise ValueError()
        return path, claims.validate_record(value, provider, identity)
    except (KeyError, ValueError, TypeError) as error:
        raise claims.ClaimError("claim_state_invalid", "Claim record is unreadable") from error


def end(directory, item, reason):
    if item["state"] == "ended":
        return
    if item["claimId"]:
        path, record = record_for_digest(directory, item["resource"])
        if record and record["active"] and record["active"]["claimId"] == item["claimId"]:
            record["active"] = None
            claims.write_record(path, record, audit_reason=reason)
    item["state"] = "ended"
    item["terminalReason"] = reason


def refresh(directory, value, now):
    for item in value["entries"]:
        if item["state"] == "ended":
            continue
        reason = None
        if not claims.process_alive(item["pid"]):
            reason = "owner_disconnected"
        elif item["heartbeat"] > now + (ACTIVE_LEASE if item["state"] in {"active", "activating"} else WAIT_LEASE) + .01:
            reason = "claim_clock_changed"
        elif now >= item["heartbeat"]:
            reason = "heartbeat_expired"
        elif item["state"] not in {"active", "activating"} and now >= item["deadline"]:
            reason = "wait_deadline_exceeded"
        elif item["state"] == "offered" and now >= item["offerDeadline"]:
            reason = "activation_offer_expired"
        if item["state"] in {"active", "activating"} and reason is None:
            _, record = record_for_digest(directory, item["resource"])
            if not record or not record["active"] or record["active"]["claimId"] != item["claimId"]:
                reason = "claim_changed"
            elif not claims.active_is_live(record["active"], claims.utc_now()):
                reason = "claim_expired"
        if reason:
            end(directory, item, reason)
    reserved = {v["resource"] for v in value["entries"] if v["state"] in {"offered", "activating", "active"}}
    for item in sorted(value["entries"], key=lambda v: v["sequence"]):
        if item["state"] != "waiting_for_resource" or item["resource"] in reserved:
            continue
        _, record = record_for_digest(directory, item["resource"])
        if record and claims.active_is_live(record["active"], claims.utc_now()):
            continue
        item["state"] = "offered"
        item["offerGeneration"] += 1
        item["offerDeadline"] = now + OFFER_LEASE
        reserved.add(item["resource"])


def sweep(directory, *, now=None):
    if not (directory / "queue.json").exists():
        return None
    value = load(directory)
    before = copy.deepcopy(value)
    refresh(directory, value, time.monotonic() if now is None else now)
    if before != value:
        value["revision"] += 1
        save(directory, value)
    return value


def before_acquire(directory, provider, identity, owner=None):
    value = sweep(directory)
    if value is None:
        return
    resource = claims.resource_digest(provider, identity)
    reserved = next((v for v in value["entries"] if v["resource"] == resource and
                     v["state"] in {"offered", "activating", "active"}), None)
    if reserved and reserved["owner"] != owner:
        raise claims.ClaimError("claim_activation_reserved", "A live queued owner has the next target offer")


class Authority:
    def __init__(self, args, *, clock=time.monotonic):
        claims.validate_policy(args)
        self.args = args
        self.provider, self.identity = claims.resource(args)
        self.resource = claims.resource_digest(self.provider, self.identity)
        self.directory = claims.state_directory(args.state_dir)
        self.clock = clock
        self.owner = secrets.token_hex(16)
        self.options = None

    def _transaction(self, task):
        with claims.store_lock(self.directory):
            value = load(self.directory)
            before = copy.deepcopy(value)
            refresh(self.directory, value, self.clock())
            try:
                result = task(value)
            finally:
                if value != before:
                    value["revision"] += 1
                    save(self.directory, value)
            if isinstance(result, dict) and result.get("schema") == SCHEMA:
                result["revision"] = value["revision"]
            return result

    def _item(self, value):
        item = next((v for v in value["entries"] if v["owner"] == self.owner), None)
        if item is None:
            raise claims.ClaimError("claim_owner_ended", "Claim connection has no live request")
        return item

    def _view(self, value, item):
        now = self.clock()
        result = {"schema": SCHEMA, "state": item["state"], "revision": value["revision"],
                  "offerGeneration": item["offerGeneration"], "assurance": "self_asserted",
                  "terminalReason": item["terminalReason"],
                  "waitRemainingSeconds": max(0, item["deadline"] - now),
                  "heartbeatRemainingSeconds": max(0, item["heartbeat"] - now),
                  "offerRemainingSeconds": max(0, item["offerDeadline"] - now) if item["state"] == "offered" else 0}
        if item["state"] == "active":
            _, record = record_for_digest(self.directory, self.resource)
            result["claim"] = claims.public_claim(record["active"], claims.utc_now())
        return result

    def submit(self, options):
        if not isinstance(options, dict) or not set(options).issubset({"waitSeconds", "reason", "claimantAuthority",
                "claimantId", "metadata", "durationSeconds", "useClass", "sessionId", "label"}):
            raise claims.ClaimError("invalid_claim_request", "Claim options are invalid")
        if self.options is not None:
            if self.options != options:
                raise claims.ClaimError("duplicate_claim_intent_changed", "This connection already has another request")
            return self.inspect()
        if type(options.get("waitSeconds")) is not int or not 1 <= options["waitSeconds"] <= 14400:
            raise claims.ClaimError("invalid_claim_request", "Claim wait deadline is invalid")
        # Reuse the exact v0 policy/attribution parser without acquiring a claim.
        parsed = copy.copy(self.args)
        parsed.reason = options.get("reason")
        parsed.claimant_authority = options.get("claimantAuthority")
        parsed.claimant_id = options.get("claimantId")
        parsed.metadata_json = json.dumps(options.get("metadata", {}))
        parsed.duration_seconds = options.get("durationSeconds")
        if parsed.duration_seconds is not None and type(parsed.duration_seconds) is not int:
            raise claims.ClaimError("invalid_claim_request", "Claim duration is invalid")
        claims.requested_duration(parsed)
        parsed.use_class = options.get("useClass", "ordinary")
        if parsed.use_class not in claims.USE_CLASSES:
            raise claims.ClaimError("invalid_claim_request", "Claim use class is invalid")
        claims.private_text(parsed.reason, "reason", claims.MAX_REASON_LENGTH)
        claims.private_text(parsed.claimant_authority, "authority", claims.MAX_IDENTITY_LENGTH)
        claims.private_text(parsed.claimant_id, "claimant ID", claims.MAX_IDENTITY_LENGTH)
        claims.validate_metadata(json.loads(parsed.metadata_json))
        parsed.session_id, parsed.label = options.get("sessionId"), options.get("label")
        for name, maximum in (("session_id", claims.MAX_IDENTITY_LENGTH), ("label", claims.MAX_LABEL_LENGTH)):
            if getattr(parsed, name) is not None:
                claims.private_text(getattr(parsed, name), name, maximum)
        self.acquire_args = parsed
        def submit(value):
            # Retain bounded recent terminal outcomes, never an unbounded diary.
            terminal = [v for v in value["entries"] if v["state"] == "ended"][-128:]
            live = [v for v in value["entries"] if v["state"] != "ended"]
            if len(live) >= MAX_ENTRIES:
                raise claims.ClaimError("claim_queue_full", "Claim waiting capacity reached")
            value["entries"] = live + terminal[:max(0, MAX_ENTRIES - len(live) - 1)]
            value["sequence"] += 1
            now = self.clock()
            item = dict(owner=self.owner, pid=os.getpid(), resource=self.resource,
                        sequence=value["sequence"], deadline=now + options["waitSeconds"],
                        heartbeat=now + WAIT_LEASE, offerDeadline=0, offerGeneration=0,
                        state="waiting_for_resource", claimId=None, terminalReason=None)
            value["entries"].append(item)
            refresh(self.directory, value, now)
            return self._view(value, item)
        result = self._transaction(submit)
        self.options = copy.deepcopy(options)
        return result

    def inspect(self, *, heartbeat=False):
        def inspect(value):
            item = self._item(value)
            if heartbeat and item["state"] != "ended":
                item["heartbeat"] = self.clock() + (ACTIVE_LEASE if item["state"] == "active" else WAIT_LEASE)
            return self._view(value, item)
        return self._transaction(inspect)

    def accept(self, generation):
        def accept(value):
            item = self._item(value)
            if type(generation) is not int or item["state"] != "offered" or generation != item["offerGeneration"]:
                raise claims.ClaimError("stale_claim_offer", "Claim offer changed or expired")
            a = self.acquire_args
            claimant = {"authority": a.claimant_authority, "id": a.claimant_id,
                        "assurance": "self_asserted", "metadata": json.loads(a.metadata_json)}
            if a.session_id is not None:
                claimant["sessionId"] = a.session_id
            if a.label is not None:
                claimant["label"] = a.label
            # Write an activation intent first. If the process dies between
            # the claim and queue writes, a later sweep can still release only
            # this exact claim. A replacement claim never matches that ID.
            item["state"] = "activating"
            item["claimId"] = f"c-{secrets.token_hex(12)}"
            item["heartbeat"] = self.clock() + ACTIVE_LEASE
            save(self.directory, value)
            try:
                claims.acquire_locked(a, self.directory, self.provider, self.identity,
                    claims.requested_duration(a), a.reason, claimant, queue_owner=self.owner,
                    claim_id=item["claimId"])
            except BaseException:
                end(self.directory, item, "activation_failed")
                raise
            item["state"] = "active"
            return self._view(value, item)
        return self._transaction(accept)

    def cancel(self):
        def cancel(value):
            item = self._item(value)
            end(self.directory, item, "cancelled")
            refresh(self.directory, value, self.clock())
            return self._view(value, item)
        return self._transaction(cancel)

    def close(self):
        if (self.directory / "queue.json").exists():
            try:
                self.cancel()
            except claims.ClaimError as error:
                if error.code != "claim_owner_ended":
                    raise
