"""Compose existing doctor, claims and workspace contracts around a local task."""

import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

import machine_control as mc
from scoped_process import ProcessTree


SCOPE_ENV = "MACHINE_CONTROL_SCOPE_FILE"
SCHEMA = "machine-control-run/v0"


def apply_scope(options, arguments):
    """Only explicitly scoped children inherit selection; no ambient fallback."""
    path = os.environ.get(SCOPE_ENV)
    if not path:
        return
    try:
        scope = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            scope["schema"] != "machine-control-scope/v0"
            or not mc._valid_claim_id(scope["claim"])
            or not isinstance(scope["target"], str) or not scope["target"]
            or not isinstance(scope["registry"], str)
            or not Path(scope["registry"]).is_absolute()
            or (scope["workspace"] is not None
                and not mc._valid_workspace_handle(scope["workspace"]))
        ):
            raise ValueError()
    except (OSError, ValueError, KeyError, TypeError):
        raise mc.ClientError("invalid_run_scope", "The task scope is unavailable")
    for key in ("registry", "target", "claim", "workspace"):
        selected = getattr(options, key)
        if selected is not None and selected != scope[key]:
            raise mc.ClientError("run_scope_conflict", "Selection conflicts with task scope")
        setattr(options, key, scope[key])
    if options.inventory_provider is not None:
        raise mc.ClientError("run_scope_conflict", "Task inventory is already selected")
    if arguments and arguments[0] in {"run", "claim", "workspace", "inventory"}:
        raise mc.ClientError(
            "run_scope_management", "The parent runner owns scope management"
        )


def usage():
    return """Usage: machine-control --target ALIAS run [OPTIONS] -- PROGRAM ARG...

Required: --reason TEXT --claimant-authority NAME --claimant-id ID
Optional: --duration 30m --wait 5m --disruptive --session-id ID --label TEXT
          --metadata KEY=VALUE (repeatable) --intent persistent|isolated|candidate

Runs a local program with inherited stdin/stdout/stderr and scoped common-client
target selection. Doctor and exact-identity claim status precede acquisition.
The runner renews the claim and releases it after task/process-tree cleanup.
--wait explicitly negotiates the live v1 queue; it cannot combine with --intent.
--intent acquires a workspace and releases its returned handle under its claim.
Workspace scopes currently accept ordinary use only. Plain scopes do not stop
the target: put any lifecycle cleanup required by your task in the task itself.
Minimized machine-control-run/v0 audit records go to stderr. A failed or unknown
cleanup returns nonzero. SIGINT/SIGTERM are handled; SIGKILL cannot be cleaned up.
"""


def parse_options(arguments):
    if "--" not in arguments:
        raise mc.ClientError("usage", "run requires -- followed by a local program")
    split = arguments.index("--")
    flags, command = arguments[:split], arguments[split + 1:]
    if not command:
        raise mc.ClientError("usage", "run requires a local program")
    intent = None
    wait = None
    rest = []
    index = 0
    while index < len(flags):
        flag = flags[index]
        if flag == "--wait" or flag.startswith("--wait="):
            if wait is not None:
                raise mc.ClientError("usage", "Supply --wait only once")
            if flag == "--wait":
                index += 1
                if index == len(flags):
                    raise mc.ClientError("usage", "--wait requires a value")
                value = flags[index]
            else:
                value = flag.partition("=")[2]
            wait = mc.parse_duration_seconds(value)
            if not 1 <= wait <= 14400:
                raise mc.ClientError("invalid_claim_request", "Claim wait must be 1..14400 seconds")
        elif flag == "--intent" or flag.startswith("--intent="):
            if intent is not None:
                raise mc.ClientError("usage", "Supply --intent only once")
            if flag == "--intent":
                index += 1
                if index == len(flags):
                    raise mc.ClientError("usage", "--intent requires a value")
                intent = flags[index]
            else:
                intent = flag.partition("=")[2]
        else:
            rest.append(flag)
        index += 1
    options = mc.claim_acquire_options(rest)
    options.wait = wait
    if wait is not None and intent is not None:
        raise mc.ClientError("workspace_queue_unsupported", "Queued workspace acquisition is not supported")
    if intent is not None and intent not in mc.WORKSPACE_INTENTS:
        raise mc.ClientError("invalid_workspace_intent", "Unsupported workspace intent")
    if intent is not None and options.disruptive:
        raise mc.ClientError(
            "workspace_use_class_unsupported", "Workspace scopes support ordinary use only"
        )
    return options, intent, command


def _private_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, separators=(",", ":"))


class Run:
    def __init__(self, alias, target, options, intent):
        self.alias = alias
        self.target = {**target, "_adapterTimeout": 120}
        self.options, self.intent = options, intent
        self.claim = None
        self.admission = None
        self.handle = None
        self.signal = None
        self.child = None
        self.claim_cleanup = "not_acquired"
        self.workspace_cleanup = "not_acquired"
        self.renewals = 0
        self.deadline = 0
        self.renew_at = 0

    def audit(self, event, **extra):
        value = {
            "schema": SCHEMA, "event": event, "logicalTarget": self.alias,
            "claimId": self.claim["claimId"] if self.claim else None,
            "workspaceHandle": self.handle, "renewals": self.renewals,
            "cleanup": {"claim": self.claim_cleanup,
                        "workspace": self.workspace_cleanup},
            **extra,
        }
        print(json.dumps(value, separators=(",", ":")), file=sys.stderr, flush=True)

    def call(self, kind, operation, arguments, *, target=None):
        _, parsed, _ = mc.run_adapter(
            target or self.target,
            [f"{kind}-{operation}", *arguments, "--json"],
            accept_json_failure=True,
        )
        # Retain independently well-formed receipt IDs even if another field
        # fails validation. Never adopt a holder from a refusal/status response.
        if (operation == "acquire" and isinstance(parsed, dict)
                and parsed.get("schema") == f"machine-control-{kind}/v0"
                and parsed.get("operation") == "acquire"
                and parsed.get("accepted") is True
                and isinstance(parsed.get("data"), dict)):
            data = parsed["data"]
            if isinstance(data.get("claim"), dict):
                candidate = data["claim"]
                if mc._valid_claim_id(candidate.get("claimId")):
                    self.claim = candidate
            if kind == "workspace" and mc._valid_workspace_handle(data.get("handle")):
                self.handle = data["handle"]
        validate = (mc.validate_claim_result if kind == "claim"
                    else mc.validate_workspace_result)
        result = validate(parsed, operation)
        if not result["accepted"]:
            if operation == "acquire":
                self.claim_cleanup = "not_acquired"
                self.workspace_cleanup = "not_acquired"
            # Adapter codes/messages are not an output-sanitization boundary.
            raise mc.ClientError(f"run_{kind}_{operation}_refused",
                                 "Scoped adapter request was refused", 1)
        if result["uncertainty"] != "none":
            raise mc.ClientError("run_effect_uncertain", "Scoped result is uncertain", 1)
        return result["data"]

    def set_lease(self, claim, started):
        expected_class = "disruptive" if self.options.disruptive else "ordinary"
        if (claim["useClass"] != expected_class
                or (self.claim and any(claim[key] != self.claim[key]
                    for key in ("claimId", "generation", "useClass")))):
            raise mc.ClientError("run_claim_mismatch", "Claim identity changed", 1)
        expires = datetime.datetime.fromisoformat(
            claim["expiresAt"].replace("Z", "+00:00")
        ).timestamp()
        deadline = min(started + claim["remainingSeconds"],
                       time.monotonic() + expires - time.time())
        remaining = deadline - time.monotonic()
        if remaining < 3:
            raise mc.ClientError("run_lease_too_short", "Insufficient live lease", 1)
        self.claim = claim
        self.deadline = deadline
        self.renew_at = time.monotonic() + remaining / 3

    def acquire(self):
        report, _ = mc.doctor(self.alias, self.target)
        if (report.get("extensions", {}).get("targetIdentity") == "unavailable"
                or any(check.get("id") == "identity" and check["status"] == "fail"
                       for check in report["checks"])):
            raise mc.ClientError("run_identity_unavailable", "Doctor could not bind identity", 1)
        # The authoritative claim-status path resolves exact private identity,
        # including on platforms whose doctor has no separate identity check.
        self.call("claim", "status", [])
        if self.signal:
            return
        args = mc.claim_acquire_adapter_arguments(self.options)
        kind = "workspace" if self.intent else "claim"
        if self.intent:
            args = ["--intent", self.intent, *args]
            self.workspace_cleanup = "unresolved"
        self.claim_cleanup = "unresolved"
        started = time.monotonic()
        if getattr(self.options, "wait", None) is not None:
            from claim_session import ClaimSession
            self.admission = ClaimSession(self.target, reason=self.options.reason,
                claimant_authority=self.options.claimant_authority, claimant_id=self.options.claimant_id,
                wait=self.options.wait, duration=self.options.duration, disruptive=self.options.disruptive,
                metadata=mc.parse_claim_metadata(self.options.metadata),
                session_id=self.options.session_id, label=self.options.label)
            self.audit("waiting")
            data = self.admission.wait(cancelled=lambda:self.signal is not None)
            started = time.monotonic()
        else:
            data = self.call(kind, "acquire", args)
        if self.intent and data["requestedIntent"] != self.intent:
            raise mc.ClientError("workspace_intent_mismatch", "Workspace intent changed", 1)
        if "claim" not in data:
            raise mc.ClientError("invalid_workspace_result", "Workspace omitted its claim", 1)
        self.set_lease(data["claim"], started)
        self.audit("acquired")

    def selected(self, *, workspace=True):
        env = {**self.target.get("environment", {}),
               "MACHINE_CONTROL_CLAIM_ID": self.claim["claimId"]}
        if workspace and self.handle:
            env["MACHINE_CONTROL_WORKSPACE_HANDLE"] = self.handle
        return {**self.target, "environment": env}

    def renew(self):
        remaining = self.deadline - time.monotonic()
        if remaining < 3:
            raise mc.ClientError("run_lease_expiring", "Claim renewal missed its deadline", 1)
        target = self.selected()
        target["_adapterTimeout"] = min(30, remaining / 3)
        args = ["--claim-id", self.claim["claimId"]]
        if self.options.duration is not None:
            args += ["--duration-seconds", str(self.options.duration)]
        started = time.monotonic()
        data = self.call("claim", "renew", args, target=target)
        self.set_lease(data["claim"], started)
        self.renewals += 1

    def environment(self, directory):
        registry = Path(directory) / "targets.json"
        scope = Path(directory) / "scope.json"
        target = {key: value for key, value in self.target.items()
                  if not key.startswith("_")}
        _private_json(registry, {"schema": mc.TARGET_SCHEMA,
                                "targets": {self.alias: target}})
        _private_json(scope, {
            "schema": "machine-control-scope/v0", "registry": str(registry),
            "target": self.alias, "claim": self.claim["claimId"],
            "workspace": self.handle,
        })
        return {**os.environ, **self.selected()["environment"],
                SCOPE_ENV: str(scope)}

    def cleanup(self):
        if self.child:
            try:
                self.child.stop(self.signal or signal.SIGTERM)
            except (OSError, subprocess.TimeoutExpired):
                # Do not release authority while a workload may still be alive.
                # A queued connection must stop renewing its liveness even
                # when process cleanup is uncertain; guarded routes fence it.
                if self.admission:
                    self.admission.close(cancel=False)
                return "run_child_cleanup_failed"
            finally:
                self.child.close()
        if not self.claim:
            if self.admission:
                self.admission.close()
                self.claim_cleanup = "not_acquired"
            return None
        try:
            if self.intent:
                if not self.handle:
                    return "run_workspace_receipt_missing"
                data = self.call("workspace", "release",
                                 ["--handle", self.handle],
                                 target=self.selected(workspace=False))
                if data["handle"] != self.handle:
                    raise mc.ClientError("run_release_mismatch", "Workspace receipt changed", 1)
                self.workspace_cleanup = "released"
            else:
                data = self.call("claim", "release",
                                 ["--claim-id", self.claim["claimId"]],
                                 target=self.selected())
                if (data["claimId"] != self.claim["claimId"]
                        or (isinstance(self.claim.get("generation"), int)
                            and data["generation"] != self.claim["generation"])):
                    raise mc.ClientError("run_release_mismatch", "Claim receipt changed", 1)
            self.claim_cleanup = "released"
        except mc.ClientError as error:
            return error.code
        finally:
            if self.admission:
                self.admission.close()
        return None


def handle_run(alias, target, arguments):
    if arguments in (["--help"], ["-h"], ["help"]):
        print(usage(), end="")
        return 0
    options, intent, command = parse_options(arguments)
    if target.get("_claimId") or target.get("_workspaceHandle"):
        raise mc.ClientError("run_scope_conflict", "run requires an unclaimed selection")
    if any(target.get("environment", {}).get(key) or os.environ.get(key)
           for key in ("MACHINE_CONTROL_CLAIM_ID", "MACHINE_CONTROL_WORKSPACE_HANDLE")):
        raise mc.ClientError("run_scope_conflict", "run cannot inherit an existing claim or workspace")
    if (target.get("claimPolicy") == "unsupported"
            or target.get("interface") != "machine-control-v0"):
        raise mc.ClientError("run_claims_unsupported", "This target has no scoped claim route")
    # Validate metadata before any adapter calls/mutation.
    mc.claim_acquire_adapter_arguments(options)
    run = Run(alias, target, options, intent)
    saved = {}
    temporary = None
    outcome, error_code, child_exit = "setup_failed", None, None
    def interrupted(signum, _frame):
        if run.signal is None:
            run.signal = signum
    try:
        for signum in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGHUP", None)):
            if signum is not None:
                saved[signum] = signal.signal(signum, interrupted)
        run.acquire()
        if not run.signal:
            temporary = tempfile.TemporaryDirectory(prefix="machine-control-run-")
            env = run.environment(temporary.name)
            # File setup/launch must not consume the lease unnoticed.
            if time.monotonic() >= run.renew_at:
                run.renew()
            run.child = ProcessTree(command, env=env)
            outcome = "completed"
            while True:
                child_exit = run.child.process.poll()
                if run.signal or child_exit is not None:
                    break
                if run.admission and (run.admission.failure or run.admission.view["state"] != "active"):
                    outcome = "claim_ended"
                    raise mc.ClientError("run_claim_admission_ended", "Queued target ownership ended", 1)
                if time.monotonic() >= run.renew_at:
                    outcome = "renewal_failed"
                    run.renew()
                    outcome = "completed"
                time.sleep(0.05)
        if child_exit not in (None, 0) and outcome == "completed":
            outcome = "child_failed"
    except mc.ClientError as error:
        if not (run.signal and error.code == "cancelled"):
            error_code = error.code
    except (OSError, ValueError):
        error_code = "run_execution_failed"
    finally:
        try:
            cleanup_error = run.cleanup()
        except OSError:
            cleanup_error = "run_cleanup_failed"
        if cleanup_error:
            error_code = cleanup_error
        if temporary:
            try:
                temporary.cleanup()
            except OSError:
                error_code = "run_scope_cleanup_failed"
        if run.signal:
            outcome = "interrupted"
        unresolved = "unresolved" in (run.claim_cleanup, run.workspace_cleanup)
        exit_code = (1 if error_code or unresolved else
                     128 + run.signal if run.signal else
                     128 - child_exit if child_exit is not None and child_exit < 0 else
                     child_exit or 0)
        try:
            run.audit("finished", outcome=outcome, childExitCode=child_exit,
                      signal=run.signal, errorCode=error_code, exitCode=exit_code)
        finally:
            for signum, handler in saved.items():
                signal.signal(signum, handler)
    return exit_code
