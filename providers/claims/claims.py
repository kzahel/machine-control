#!/usr/bin/env python3
"""Private exact-resource target-use claims with minimized public results."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import sys
import time
from typing import Any, Iterator


RECORD_SCHEMA = "machine-control-target-claim-record/v0"
RESULT_SCHEMA = "machine-control-claim/v0"
CAPABILITIES_SCHEMA = "machine-control-claim-capabilities/v0"
CLAIM_PATTERN = re.compile(r"c-[a-f0-9]{24}")
USE_CLASSES = ("ordinary", "disruptive")
MAX_REASON_LENGTH = 512
MAX_IDENTITY_LENGTH = 128
MAX_LABEL_LENGTH = 256
MAX_METADATA_ENTRIES = 16
MAX_METADATA_KEY_LENGTH = 64
MAX_METADATA_VALUE_LENGTH = 256
MAX_METADATA_BYTES = 4096
LOCK_TIMEOUT_SECONDS = 5.0
STALE_LOCK_GRACE_SECONDS = LOCK_TIMEOUT_SECONDS


class ClaimError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.data = data or {}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ClaimError("claim_state_invalid", f"Claim {field} is invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ClaimError(
            "claim_state_invalid", f"Claim {field} is invalid"
        ) from error
    return parsed.astimezone(timezone.utc)


def private_text(value: Any, field: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or "\0" in value
    ):
        raise ClaimError("invalid_claim_request", f"Claim {field} is invalid")
    return value


def state_directory(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ClaimError(
            "claim_state_invalid", "Claim state directory must be absolute"
        )
    if path.exists() and (not path.is_dir() or path.is_symlink()):
        raise ClaimError(
            "claim_state_invalid", "Claim state path is not a private directory"
        )
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        path.chmod(0o700)
    return path


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return windows_process_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def windows_process_alive(pid: int) -> bool:
    # os.kill(pid, 0) shares the value of CTRL_C_EVENT on Windows and can
    # interrupt the caller's console process group during real contention.
    # Querying a process handle is read-only and does not signal the owner.
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    error_invalid_parameter = 87
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(
        process_query_limited_information, False, pid
    )
    if not handle:
        # An invalid PID is absent. Access-denied and unexpected failures are
        # treated as alive so stale-lock recovery remains fail-closed.
        return ctypes.get_last_error() != error_invalid_parameter
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def remove_stale_lock(lock: Path) -> bool:
    # A lock owner can release its directory and exit after another process
    # reads the PID. Without a grace period, a third process can then create a
    # new lock at the same path and have that live lock renamed as stale (an
    # ABA race). Normal claim operations are short, so only inspect an owner
    # after the lock has remained unchanged for a full lock timeout.
    try:
        if time.time() - lock.stat().st_mtime < STALE_LOCK_GRACE_SECONDS:
            return False
    except OSError:
        return False
    pid_path = lock / "pid"
    try:
        value = pid_path.read_text(encoding="ascii").strip()
        pid = int(value)
    except (OSError, ValueError):
        return False
    if process_alive(pid):
        return False
    stale = lock.parent / f".{lock.name}.stale.{secrets.token_hex(8)}"
    try:
        lock.rename(stale)
    except OSError:
        return False
    try:
        (stale / "pid").unlink()
        stale.rmdir()
    except OSError as error:
        raise ClaimError(
            "claim_state_invalid", "Stale claim lock contained unexpected state"
        ) from error
    return True


@contextmanager
def store_lock(directory: Path) -> Iterator[None]:
    lock = directory / ".operation.lock"
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock.mkdir(mode=0o700)
            (lock / "pid").write_text(f"{os.getpid()}\n", encoding="ascii")
            if os.name != "nt":
                (lock / "pid").chmod(0o600)
            break
        except FileExistsError:
            if remove_stale_lock(lock):
                continue
            if time.monotonic() >= deadline:
                raise ClaimError(
                    "claim_store_busy", "Another claim operation is active"
                )
            time.sleep(0.02)
        except OSError as error:
            raise ClaimError(
                "claim_state_invalid", "Claim operation lock is unavailable"
            ) from error
    try:
        yield
    finally:
        try:
            (lock / "pid").unlink(missing_ok=True)
            lock.rmdir()
        except OSError:
            pass


def resource_digest(provider: str, resource_id: str) -> str:
    value = f"{provider}\0{resource_id}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def record_path(directory: Path, provider: str, resource_id: str) -> Path:
    return directory / f"resource-{resource_digest(provider, resource_id)}.json"


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, separators=(",", ":"), sort_keys=True)
            output.write("\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    if os.name != "nt":
        path.chmod(0o600)


def write_record(path: Path, value: dict[str, Any]) -> None:
    temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}"
    write_exclusive(temporary, value)
    os.replace(temporary, path)
    if os.name != "nt":
        path.chmod(0o600)


def new_record(provider: str, resource_id: str) -> dict[str, Any]:
    return {
        "schema": RECORD_SCHEMA,
        "resource": {"provider": provider, "id": resource_id},
        "generation": 0,
        "active": None,
    }


def validate_metadata(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or len(value) > MAX_METADATA_ENTRIES:
        raise ClaimError(
            "invalid_claim_request", "Claim metadata must be a bounded object"
        )
    result: dict[str, str] = {}
    for key, item in value.items():
        if (
            not isinstance(key, str)
            or not key
            or len(key) > MAX_METADATA_KEY_LENGTH
            or "\0" in key
            or not isinstance(item, str)
            or len(item) > MAX_METADATA_VALUE_LENGTH
            or "\0" in item
        ):
            raise ClaimError(
                "invalid_claim_request",
                "Claim metadata keys or values are invalid",
            )
        result[key] = item
    if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > MAX_METADATA_BYTES:
        raise ClaimError(
            "invalid_claim_request", "Claim metadata is too large"
        )
    return result


def validate_claim(value: Any, generation: int) -> dict[str, Any]:
    legacy_required = {
        "claimId",
        "mode",
        "generation",
        "claimant",
        "reason",
        "acquiredAt",
        "renewedAt",
        "expiresAt",
        "maxExpiresAt",
    }
    if isinstance(value, dict) and set(value) == legacy_required:
        # Records written before use classes existed must remain usable, but
        # can never gain disruptive access through compatibility defaulting.
        value["useClass"] = "ordinary"
    required = legacy_required | {"useClass"}
    if not isinstance(value, dict) or set(value) != required:
        raise ClaimError("claim_state_invalid", "Active claim shape is invalid")
    if (
        not isinstance(value.get("claimId"), str)
        or CLAIM_PATTERN.fullmatch(value["claimId"]) is None
        or value.get("mode") != "exclusive"
        or value.get("useClass") not in USE_CLASSES
        or value.get("generation") != generation
    ):
        raise ClaimError("claim_state_invalid", "Active claim value is invalid")
    claimant = value.get("claimant")
    allowed_claimant = {
        "authority", "id", "assurance", "metadata", "sessionId", "label"
    }
    required_claimant = {"authority", "id", "assurance", "metadata"}
    if (
        not isinstance(claimant, dict)
        or not required_claimant.issubset(claimant)
        or not set(claimant).issubset(allowed_claimant)
        or claimant.get("assurance") != "self_asserted"
    ):
        raise ClaimError("claim_state_invalid", "Claimant value is invalid")
    private_text(claimant.get("authority"), "authority", MAX_IDENTITY_LENGTH)
    private_text(claimant.get("id"), "claimant ID", MAX_IDENTITY_LENGTH)
    if "sessionId" in claimant:
        private_text(claimant["sessionId"], "session ID", MAX_IDENTITY_LENGTH)
    if "label" in claimant:
        private_text(claimant["label"], "label", MAX_LABEL_LENGTH)
    validate_metadata(claimant.get("metadata"))
    private_text(value.get("reason"), "reason", MAX_REASON_LENGTH)
    acquired = parse_timestamp(value.get("acquiredAt"), "acquiredAt")
    renewed = parse_timestamp(value.get("renewedAt"), "renewedAt")
    expires = parse_timestamp(value.get("expiresAt"), "expiresAt")
    maximum = parse_timestamp(value.get("maxExpiresAt"), "maxExpiresAt")
    if not acquired <= renewed < expires <= maximum:
        raise ClaimError("claim_state_invalid", "Claim timestamps are invalid")
    return value


def validate_record(
    value: Any, provider: str, resource_id: str
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "resource", "generation", "active"}
        or value.get("schema") != RECORD_SCHEMA
        or not isinstance(value.get("generation"), int)
        or isinstance(value.get("generation"), bool)
        or value["generation"] < 0
    ):
        raise ClaimError("claim_state_invalid", "Claim record is invalid")
    resource = value.get("resource")
    if (
        not isinstance(resource, dict)
        or set(resource) != {"provider", "id"}
        or resource.get("provider") != provider
        or resource.get("id") != resource_id
    ):
        raise ClaimError(
            "claim_identity_mismatch",
            "Claim record does not match the exact target identity",
        )
    if value["active"] is not None:
        validate_claim(value["active"], value["generation"])
    return value


def load_record(
    directory: Path, provider: str, resource_id: str
) -> tuple[Path, dict[str, Any]]:
    path = record_path(directory, provider, resource_id)
    if not path.exists():
        return path, new_record(provider, resource_id)
    if not path.is_file() or path.is_symlink():
        raise ClaimError("claim_state_invalid", "Claim record entry is unsafe")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ClaimError("claim_state_invalid", "Claim record is unreadable") from error
    return path, validate_record(value, provider, resource_id)


def active_is_live(active: dict[str, Any] | None, now: datetime) -> bool:
    if active is None:
        return False
    acquired = parse_timestamp(active["acquiredAt"], "acquiredAt")
    if now < acquired:
        raise ClaimError(
            "claim_clock_invalid",
            "Controller time is earlier than the recorded claim acquisition",
        )
    return parse_timestamp(active["expiresAt"], "expiresAt") > now


def public_claim(active: dict[str, Any], now: datetime) -> dict[str, Any]:
    result = dict(active)
    result["claimant"] = dict(active["claimant"])
    expires = parse_timestamp(active["expiresAt"], "expiresAt")
    result["remainingSeconds"] = max(
        0, math.ceil((expires - now).total_seconds())
    )
    return result


def accepted(operation: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "operation": operation,
        "accepted": True,
        "uncertainty": "none",
        "data": data,
    }


def refused(error: ClaimError, operation: str) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "operation": operation,
        "accepted": False,
        "uncertainty": "none",
        "errorCode": error.code,
        "message": str(error),
        "data": error.data,
    }


def validate_policy(args: argparse.Namespace) -> None:
    values = (
        args.minimum_duration,
        args.default_duration,
        args.maximum_duration,
        args.maximum_lifetime,
    )
    if (
        any(not isinstance(item, int) or item < 1 for item in values)
        or not args.minimum_duration
        <= args.default_duration
        <= args.maximum_duration
        <= args.maximum_lifetime
    ):
        raise ClaimError("claim_policy_invalid", "Claim duration policy is invalid")


def requested_duration(args: argparse.Namespace) -> int:
    duration = args.duration_seconds or args.default_duration
    if not args.minimum_duration <= duration <= args.maximum_duration:
        raise ClaimError(
            "invalid_claim_duration",
            "Claim duration is outside the configured policy",
        )
    return duration


def resource(args: argparse.Namespace) -> tuple[str, str]:
    provider = private_text(args.provider, "provider", MAX_IDENTITY_LENGTH)
    resource_id = private_text(
        args.resource_id, "resource identity", MAX_METADATA_BYTES
    )
    return provider, resource_id


def command_capabilities(args: argparse.Namespace) -> dict[str, Any]:
    validate_policy(args)
    return {
        "schema": CAPABILITIES_SCHEMA,
        "mode": "exclusive",
        "useClasses": {
            "supported": list(USE_CLASSES),
            "default": "ordinary",
        },
        "durations": {
            "defaultSeconds": args.default_duration,
            "minimumSeconds": args.minimum_duration,
            "maximumSeconds": args.maximum_duration,
            "maximumLifetimeSeconds": args.maximum_lifetime,
        },
        "claimant": {
            "assurance": ["self_asserted"],
            "maximumMetadataEntries": MAX_METADATA_ENTRIES,
            "maximumMetadataBytes": MAX_METADATA_BYTES,
        },
        "resourceBinding": "exact_private_identity",
        "queueing": False,
    }


def command_acquire(args: argparse.Namespace) -> dict[str, Any]:
    validate_policy(args)
    provider, resource_id = resource(args)
    duration = requested_duration(args)
    use_class = args.use_class
    if use_class not in USE_CLASSES:
        raise ClaimError(
            "invalid_claim_request", "Claim use class is invalid"
        )
    reason = private_text(args.reason, "reason", MAX_REASON_LENGTH)
    claimant: dict[str, Any] = {
        "authority": private_text(
            args.claimant_authority, "authority", MAX_IDENTITY_LENGTH
        ),
        "id": private_text(args.claimant_id, "claimant ID", MAX_IDENTITY_LENGTH),
        "assurance": "self_asserted",
        "metadata": validate_metadata(json.loads(args.metadata_json)),
    }
    if args.session_id is not None:
        claimant["sessionId"] = private_text(
            args.session_id, "session ID", MAX_IDENTITY_LENGTH
        )
    if args.label is not None:
        claimant["label"] = private_text(args.label, "label", MAX_LABEL_LENGTH)
    directory = state_directory(args.state_dir)
    with store_lock(directory):
        now = utc_now()
        path, record = load_record(directory, provider, resource_id)
        active = record["active"]
        if active_is_live(active, now):
            assert active is not None
            raise ClaimError(
                "target_claimed",
                "The exact target already has an active exclusive claim",
                data={"state": "held", "claim": public_claim(active, now)},
            )
        generation = record["generation"] + 1
        acquired = now
        maximum = acquired + timedelta(seconds=args.maximum_lifetime)
        expires = acquired + timedelta(seconds=duration)
        active = {
            "claimId": f"c-{secrets.token_hex(12)}",
            "mode": "exclusive",
            "useClass": use_class,
            "generation": generation,
            "claimant": claimant,
            "reason": reason,
            "acquiredAt": timestamp(acquired),
            "renewedAt": timestamp(acquired),
            "expiresAt": timestamp(expires),
            "maxExpiresAt": timestamp(maximum),
        }
        record["generation"] = generation
        record["active"] = active
        validate_record(record, provider, resource_id)
        write_record(path, record)
    return accepted("acquire", {"state": "held", "claim": public_claim(active, now)})


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    validate_policy(args)
    provider, resource_id = resource(args)
    directory = state_directory(args.state_dir)
    with store_lock(directory):
        now = utc_now()
        _, record = load_record(directory, provider, resource_id)
    active = record["active"]
    data: dict[str, Any] = {
        "state": "available",
        "generation": record["generation"],
    }
    if active_is_live(active, now):
        assert active is not None
        data = {"state": "held", "claim": public_claim(active, now)}
    return accepted("status", data)


def require_matching_live_claim(
    record: dict[str, Any], claim_id: str, now: datetime
) -> dict[str, Any]:
    active = record["active"]
    if active is None:
        raise ClaimError("claim_not_held", "The exact target has no active claim")
    if active["claimId"] != claim_id:
        if active_is_live(active, now):
            raise ClaimError(
                "claim_mismatch",
                "A different exclusive claim currently holds the exact target",
                data={"state": "held", "claim": public_claim(active, now)},
            )
        raise ClaimError("claim_expired", "The supplied target-use claim is stale")
    if not active_is_live(active, now):
        raise ClaimError("claim_expired", "The supplied target-use claim has expired")
    return active


def command_check(args: argparse.Namespace) -> dict[str, Any]:
    validate_policy(args)
    provider, resource_id = resource(args)
    claim_id = private_text(args.claim_id, "claim ID", MAX_IDENTITY_LENGTH)
    if CLAIM_PATTERN.fullmatch(claim_id) is None:
        raise ClaimError("invalid_claim_id", "Target-use claim ID is invalid")
    directory = state_directory(args.state_dir)
    with store_lock(directory):
        now = utc_now()
        _, record = load_record(directory, provider, resource_id)
        active = require_matching_live_claim(record, claim_id, now)
        required_use_class = args.required_use_class
        if required_use_class not in {None, *USE_CLASSES}:
            raise ClaimError(
                "invalid_claim_request", "Required claim use class is invalid"
            )
        if (
            required_use_class == "disruptive"
            and active["useClass"] != "disruptive"
        ):
            raise ClaimError(
                "disruptive_claim_required",
                "Host-visible VM capture or input requires a disruptive claim",
                data={"state": "held", "claim": public_claim(active, now)},
            )
    return accepted("check", {
        "state": "held",
        "claimId": active["claimId"],
        "generation": active["generation"],
        "expiresAt": active["expiresAt"],
    })


def command_renew(args: argparse.Namespace) -> dict[str, Any]:
    validate_policy(args)
    provider, resource_id = resource(args)
    duration = requested_duration(args)
    claim_id = private_text(args.claim_id, "claim ID", MAX_IDENTITY_LENGTH)
    if CLAIM_PATTERN.fullmatch(claim_id) is None:
        raise ClaimError("invalid_claim_id", "Target-use claim ID is invalid")
    directory = state_directory(args.state_dir)
    with store_lock(directory):
        now = utc_now()
        path, record = load_record(directory, provider, resource_id)
        active = require_matching_live_claim(record, claim_id, now)
        maximum = parse_timestamp(active["maxExpiresAt"], "maxExpiresAt")
        expires = min(now + timedelta(seconds=duration), maximum)
        if expires <= now:
            raise ClaimError(
                "claim_lifetime_exceeded",
                "The target-use claim reached its maximum continuous lifetime",
            )
        active["renewedAt"] = timestamp(now)
        active["expiresAt"] = timestamp(expires)
        validate_record(record, provider, resource_id)
        write_record(path, record)
    return accepted("renew", {"state": "held", "claim": public_claim(active, now)})


def command_release(args: argparse.Namespace) -> dict[str, Any]:
    validate_policy(args)
    provider, resource_id = resource(args)
    claim_id = private_text(args.claim_id, "claim ID", MAX_IDENTITY_LENGTH)
    if CLAIM_PATTERN.fullmatch(claim_id) is None:
        raise ClaimError("invalid_claim_id", "Target-use claim ID is invalid")
    directory = state_directory(args.state_dir)
    with store_lock(directory):
        now = utc_now()
        path, record = load_record(directory, provider, resource_id)
        active = record["active"]
        disposition = "alreadyReleased"
        if active is not None and active_is_live(active, now):
            if active["claimId"] != claim_id:
                raise ClaimError(
                    "claim_mismatch",
                    "A different exclusive claim currently holds the exact target",
                    data={"state": "held", "claim": public_claim(active, now)},
                )
            record["active"] = None
            write_record(path, record)
            disposition = "released"
        elif active is not None and active["claimId"] == claim_id:
            record["active"] = None
            write_record(path, record)
    return accepted("release", {
        "claimId": claim_id,
        "generation": record["generation"],
        "disposition": disposition,
    })


def add_resource_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", required=True)
    parser.add_argument("--resource-id", required=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--state-dir", required=True)
    result.add_argument("--minimum-duration", type=int, default=60)
    result.add_argument("--default-duration", type=int, default=1800)
    result.add_argument("--maximum-duration", type=int, default=14400)
    result.add_argument("--maximum-lifetime", type=int, default=14400)
    commands = result.add_subparsers(dest="command", required=True)

    capabilities = commands.add_parser("capabilities")
    capabilities.set_defaults(function=command_capabilities)

    acquire = commands.add_parser("acquire")
    add_resource_arguments(acquire)
    acquire.add_argument("--duration-seconds", type=int)
    acquire.add_argument("--reason", required=True)
    acquire.add_argument("--claimant-authority", required=True)
    acquire.add_argument("--claimant-id", required=True)
    acquire.add_argument("--session-id")
    acquire.add_argument("--label")
    acquire.add_argument("--metadata-json", default="{}")
    acquire.add_argument(
        "--disruptive",
        dest="use_class",
        action="store_const",
        const="disruptive",
        default="ordinary",
    )
    acquire.set_defaults(function=command_acquire)

    status = commands.add_parser("status")
    add_resource_arguments(status)
    status.set_defaults(function=command_status)

    for name, function in (
        ("check", command_check),
        ("renew", command_renew),
        ("release", command_release),
    ):
        operation = commands.add_parser(name)
        add_resource_arguments(operation)
        operation.add_argument("--claim-id", required=True)
        if name == "check":
            operation.add_argument(
                "--required-use-class", choices=USE_CLASSES
            )
        if name == "renew":
            operation.add_argument("--duration-seconds", type=int)
        operation.set_defaults(function=function)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        value = args.function(args)
    except json.JSONDecodeError:
        error = ClaimError(
            "invalid_claim_request", "Claim metadata JSON is invalid"
        )
        print(json.dumps(refused(error, args.command), separators=(",", ":")))
        return 1
    except ClaimError as error:
        print(json.dumps(refused(error, args.command), separators=(",", ":")))
        return 1
    except OSError:
        error = ClaimError(
            "claim_state_invalid", "Private claim state could not be updated"
        )
        print(json.dumps(refused(error, args.command), separators=(",", ":")))
        return 1
    print(json.dumps(value, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
