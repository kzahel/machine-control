#!/usr/bin/env python3
"""Private live adapter transport for v1 queued target-use claims."""
import argparse
import json
import os
import queue
import sys
import threading
import time

import admission
import claims

CHANNEL_SCHEMA = "machine-control-claim-channel/v1"


def run(args):
    authority = admission.Authority(args)
    incoming, outgoing = queue.Queue(maxsize=8), queue.Queue(maxsize=8)
    stopped = threading.Event()
    parent = os.getppid()

    def read():
        try:
            while not stopped.is_set():
                line = sys.stdin.buffer.readline(65537)
                if not line or not line.endswith(b"\n") or len(line) > 65536:
                    break
                while not stopped.is_set():
                    try:
                        incoming.put(line, timeout=.1)
                        break
                    except queue.Full:
                        continue
        finally:
            stopped.set()

    def write():
        try:
            while not stopped.is_set():
                try:
                    frame, deadline = outgoing.get(timeout=.1)
                except queue.Empty:
                    continue
                # The watchdog observes a stalled writer without depending on
                # this blocking pipe write or on a client's next frame.
                writing[0] = deadline
                sys.stdout.buffer.write(frame)
                sys.stdout.buffer.flush()
                writing[0] = None
        except (OSError, ValueError):
            stopped.set()

    writing = [None]
    threading.Thread(target=read, daemon=True).start()
    threading.Thread(target=write, daemon=True).start()
    seen = set()
    sequence = None
    opened = False
    initial_deadline = time.monotonic() + 5
    try:
        while not stopped.is_set():
            if os.getppid() != parent or writing[0] is not None and time.monotonic() >= writing[0]:
                break
            if not opened and time.monotonic() >= initial_deadline:
                break
            if opened:
                authority.inspect()  # expiry/liveness independently of polling
            try:
                line = incoming.get(timeout=.1)
            except queue.Empty:
                continue
            request = json.loads(line)
            if not isinstance(request, dict):
                break
            identifier = request.get("requestId")
            if not isinstance(identifier, str) or not identifier or len(identifier) > 80:
                break
            if sequence is not None or "requestSequence" in request:
                supplied = request.get("requestSequence")
                if type(supplied) is not int or supplied != (sequence or 0) + 1 or supplied > 2**63 - 1:
                    break
                sequence = supplied
            else:
                if identifier in seen or len(seen) >= 4096:
                    break
                seen.add(identifier)
            operation = request.get("operation")
            fields = {"operation", "requestId", "requestSequence"}
            if operation == "claim.open":
                fields |= {"schema", "reason", "claimantAuthority", "claimantId", "waitSeconds",
                           "durationSeconds", "useClass", "metadata", "sessionId", "label"}
            elif operation == "claim.accept":
                fields.add("offerGeneration")
            result = {"schema": CHANNEL_SCHEMA, "requestId": identifier, "accepted": False}
            try:
                if not set(request).issubset(fields):
                    raise claims.ClaimError("invalid_claim_request", "Unexpected claim frame fields")
                if operation == "claim.open":
                    if request.get("schema") != admission.SCHEMA:
                        raise claims.ClaimError("claim_admission_unsupported", "Explicit claim admission v1 is required")
                    value = authority.submit({k: v for k, v in request.items()
                                              if k not in {"schema", "operation", "requestId", "requestSequence"}})
                    opened = True
                elif not opened:
                    raise claims.ClaimError("claim_owner_ended", "Open a claim request first")
                elif operation in {"claim.status", "claim.heartbeat"}:
                    value = authority.inspect(heartbeat=operation == "claim.heartbeat")
                elif operation == "claim.accept":
                    value = authority.accept(request.get("offerGeneration"))
                elif operation == "claim.cancel":
                    value = authority.cancel()
                else:
                    raise claims.ClaimError("unsupported_claim_operation", "Unsupported claim frame")
                result.update(accepted=True, data=value)
            except claims.ClaimError as error:
                result["errorCode"] = error.code
            frame = json.dumps(result, separators=(",", ":")).encode() + b"\n"
            try:
                outgoing.put((frame, time.monotonic() + 5), timeout=.1)
            except queue.Full:
                break
    except (OSError, ValueError, claims.ClaimError):
        pass
    finally:
        stopped.set()
        try:
            authority.close()
        except (OSError, claims.ClaimError):
            pass  # claim checks fail closed on unusable queue state
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--resource-id", required=True)
    parser.add_argument("--minimum-duration", type=int, default=60)
    parser.add_argument("--default-duration", type=int, default=1800)
    parser.add_argument("--maximum-duration", type=int, default=14400)
    parser.add_argument("--maximum-lifetime", type=int, default=14400)
    return run(parser.parse_args())


if __name__ == "__main__":
    # A blocked stdout writer must not hang Python's final stream flush after
    # the independently watched connection has ended and released its claim.
    try:
        code = main()
    except (OSError, ValueError, claims.ClaimError):
        code = 1
    os._exit(code)
