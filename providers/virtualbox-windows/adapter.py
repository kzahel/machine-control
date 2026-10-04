#!/usr/bin/env python3
"""Experimental Windows-host VirtualBox adapter; private exact-identity pins."""
from __future__ import annotations

import base64
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "providers/claims"))
import claims  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from images import Images  # noqa: E402


def parse_info(text):
    result = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = json.loads(key) if key.startswith('"') else key
        if key in result:
            raise ValueError("Duplicate management field")
        if value.startswith('"'):
            try:
                decoded, end = json.JSONDecoder().raw_decode(value)
            except json.JSONDecodeError:
                # Some ancillary fields (e.g. uartmode) contain unescaped
                # Windows paths. Preserve them verbatim. Identity fields
                # still fail closed against their canonical private pins.
                result[key] = value
                continue
            # VideoMode is a composite such as "1280,800,32"@0,0 1.
            # Preserve trailing data; never truncate a malformed identity.
            result[key] = decoded if end == len(value) else value
        else:
            result[key] = value
    return result


def load_config(path):
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if value.get("schema") != "machine-control-virtualbox-target/v0":
        raise ValueError("Invalid private configuration schema")
    if value.get("platform") not in {"windows", "linux"}:
        raise ValueError("Unsupported guest platform")
    if value.get("role") not in {"candidate", "development"}:
        raise ValueError("Unqualified target role")
    if str(uuid.UUID(value["uuid"])) != value["uuid"]:
        raise ValueError("Exact UUID required")
    uuid.UUID(value["diskUuid"])
    for key in ("library", "vmFile", "disk", "stateDirectory", "sshKey", "knownHosts"):
        if not Path(value[key]).is_absolute():
            raise ValueError("Absolute private locators required")
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_.-]{0,31}", value["username"]):
        raise ValueError("Invalid guest account selector")
    if type(value["sshPort"]) is not int or not 1 <= value["sshPort"] <= 65535:
        raise ValueError("Invalid loopback transport")
    if not isinstance(value.get("profile"), str) or not value["profile"]:
        raise ValueError("Guest profile required")
    assist = value.get("shutdownRescheduleAfterSeconds", 0)
    if type(assist) is not int or assist != 0 and not 15 <= assist <= 120:
        raise ValueError("Shutdown reschedule must be disabled or bounded to 15..120 seconds")
    if assist and value["platform"] != "windows":
        raise ValueError("Shutdown reschedule is a Windows-only compatibility experiment")
    connect_timeout = value.get("sshConnectTimeoutSeconds", 5)
    if type(connect_timeout) is not int or not 5 <= connect_timeout <= 60:
        raise ValueError("SSH connection deadline must be bounded to 5..60 seconds")
    return value


class Adapter:
    def __init__(self, config):
        self.config = config
        self.environment = {**os.environ, "VBOX_USER_HOME": config["library"]}
        self.executable = str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) /
                              "Oracle/VirtualBox/VBoxManage.exe")
        self.state = Path(config["stateDirectory"])
        # A copied UUID in another isolated library is a distinct resource.
        self.resource = hashlib.sha256((str(Path(config["library"]).resolve()).casefold() +
                                       "\0" + config["uuid"]).encode()).hexdigest()

    def vbox(self, *arguments):
        result = subprocess.run([self.executable, *map(str, arguments)],
                                env=self.environment, capture_output=True, text=True,
                                timeout=60)
        if result.returncode:
            raise ValueError("VirtualBox management failed; inspect private provider logs")
        return result.stdout

    def inspect(self):
        value = parse_info(self.vbox("showvminfo", self.config["uuid"], "--machinereadable"))
        if value.get("UUID") != self.config["uuid"]:
            raise ValueError("VM identity mismatch")
        for field, key in (("CfgFile", "vmFile"), ("SATA-0-0", "disk")):
            if Path(value.get(field, "")).resolve() != Path(self.config[key]).resolve():
                raise ValueError("VM registration or disk path mismatch")
        if value.get("SATA-ImageUUID-0-0") != self.config["diskUuid"]:
            raise ValueError("Disk identity mismatch")
        return value

    def claim(self, operation, arguments=()):
        args = [sys.executable, str(ROOT / "providers/claims/claims.py"),
                "--state-dir", str(self.state / "claims"), operation]
        if operation != "capabilities":
            args += ["--provider", "virtualbox-windows", "--resource-id", self.resource]
        return subprocess.run([*args, *arguments], capture_output=True, text=True)

    def require_claim(self, disruptive=False):
        identifier = os.environ.get("MACHINE_CONTROL_CLAIM_ID", "")
        if not re.fullmatch(r"c-[a-f0-9]{24}", identifier):
            raise ValueError("Exclusive target claim required")
        arguments = ["--claim-id", identifier]
        if disruptive:
            arguments += ["--required-use-class", "disruptive"]
        result = self.claim("check", arguments)
        if result.returncode or json.loads(result.stdout).get("accepted") is not True:
            raise ValueError("Exclusive claim is missing, stale, or mismatched")

    def ssh_arguments(self, command):
        c = self.config
        executable = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/OpenSSH/ssh.exe"
        return [str(executable), "-F", "NUL", "-T", "-i", c["sshKey"], "-p", str(c["sshPort"]),
                "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
                "-o", "StrictHostKeyChecking=yes", "-o",
                "ConnectTimeout=" + str(c.get("sshConnectTimeoutSeconds", 5)),
                "-o", "UserKnownHostsFile=" + c["knownHosts"], c["username"] + "@127.0.0.1", command]

    def ssh(self, command, input_bytes=None, timeout=120):
        result = subprocess.run(self.ssh_arguments(command), input=input_bytes,
                                capture_output=True, timeout=timeout)
        if result.returncode:
            raise ValueError("Guest command failed; no host or console fallback")
        return result.stdout.decode("utf-8-sig").strip()

    def powershell(self, script, input_bytes=None, timeout=120):
        script = "[Console]::OutputEncoding=[Text.UTF8Encoding]::new();" + script
        encoded = base64.b64encode(script.encode("utf-16le")).decode()
        return self.ssh("& 'C:\\Program Files\\PowerShell\\7\\pwsh.exe' "
                        "-NoLogo -NoProfile -NonInteractive -EncodedCommand " + encoded,
                        input_bytes, timeout)

    def control(self, request):
        if self.config["platform"] == "windows":
            encoded = base64.b64encode(json.dumps(request).encode()).decode()
            return json.loads(self.powershell(
                "$j=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + encoded +
                "'));$j | & 'C:\\ProgramData\\MachineControl\\runtime\\machine-control-windows.exe' call;"
                "exit $LASTEXITCODE"))
        command = "XDG_RUNTIME_DIR=/run/user/$(id -u) /usr/local/bin/machine-control "
        return json.loads(self.ssh(command + shlex.quote(json.dumps(request))))

    def login(self):
        """Cold login through the existing appliance's one-shot secret pipe."""
        identity = json.loads(self.powershell(
            "[ordered]@{user=[Environment]::UserName;"
            "display=(Get-LocalUser -Name $env:USERNAME).FullName}|ConvertTo-Json -Compress"))
        if identity.get("user", "").casefold() != self.config["username"].casefold() or \
                not identity.get("display"):
            raise ValueError("Authenticated account display identity is unavailable")
        status = self.control({"operation": "service.status"})
        if not status.get("accepted") or status.get("data", {}).get("interactiveUserPresent") is not False:
            raise ValueError("Cold login requires no interactive user; use authorized unlock otherwise")
        request = dict(operation="snapshot", scope="system", maxDepth=14, maxElements=150)
        surface = self.control(request)
        if not surface.get("accepted") or surface.get("desktop") != "Winlogon":
            raise ValueError("Native Winlogon discovery is unavailable")
        elements = surface.get("data", {}).get("elements", [])
        if elements and len(elements) < 150 and not any(e.get("controlType") == "Edit" for e in elements):
            reveal = self.control(dict(operation="key", key="enter",
                                       expectedGeneration=surface["generation"]))
            if not reveal.get("accepted"):
                raise ValueError("Credential surface reveal was not accepted")
            surface = self.control(request)
        elements = surface.get("data", {}).get("elements", [])
        fields = [e for e in elements if e.get("controlType") == "Edit" and
                  e.get("automationId", "").startswith("PasswordField_") and
                  e.get("name") == "Password" and e.get("enabled") and not e.get("offscreen")]
        account_bound = False
        ancestors = []
        for element in elements:
            depth = element.get("depth")
            if type(depth) is not int:
                ancestors = []
                continue
            while ancestors and ancestors[-1]["depth"] >= depth:
                ancestors.pop()
            if len(fields) == 1 and element is fields[0]:
                account_bound = any(e.get("controlType") == "Group" and
                                    e.get("name") == identity["display"] and
                                    not e.get("offscreen") for e in ancestors)
            ancestors.append(element)
        if not surface.get("accepted") or surface.get("desktop") != "Winlogon" or \
                len(elements) >= 150 or len(fields) != 1 or not account_bound:
            raise ValueError("Exact account and stock password field discovery is uncertain")
        locator = Path(self.config.get("credentialFile", ""))
        if not locator.is_absolute() or not locator.is_file():
            raise ValueError("Canonical credential locator is unavailable")
        self.require_claim()
        self.inspect()
        secret = locator.read_bytes().rstrip(b"\r\n")
        try:
            # The broker independently revalidates session/provider/field state.
            return json.loads(self.ssh(
                "& 'C:\\ProgramData\\MachineControl\\runtime\\machine-control-windows.exe' "
                "login --kind password", secret, timeout=75))
        finally:
            secret = None

    def credential(self, verify=False):
        locator = Path(self.config.get("credentialFile", ""))
        record = self.state / "credential-verification.json"
        if not locator.is_absolute() or not locator.is_file():
            raise ValueError("Canonical credential locator is unavailable")
        fingerprint = dict(size=locator.stat().st_size, modified=locator.stat().st_mtime_ns)
        if verify:
            if self.config["platform"] == "windows":
                if self.powershell("[Environment]::UserName").casefold() != self.config["username"].casefold():
                    raise ValueError("Guest account identity mismatch")
                source = (ROOT / "platforms/windows/scripts/credential.sh").read_text()
                match = re.search(r"^readonly VALIDATE_SCRIPT='([^']*)'$", source, re.MULTILINE)
                if not match:
                    raise ValueError("Authoritative Windows credential verifier is unavailable")
                # Reuse the Windows credential verifier with dedicated stdin.
                if self.powershell(match.group(1), locator.read_bytes()) != "valid":
                    raise ValueError("Guest password verification failed")
            else:
                if self.ssh("id -un") != self.config["username"]:
                    raise ValueError("Guest account identity mismatch")
                spec = importlib.util.spec_from_file_location("linux_credential",
                    ROOT / "platforms/linux/scripts/credential.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                # Only read after exact identity and authenticated transport checks.
                secret = locator.read_bytes()
                result = self.ssh("sudo python3 -W ignore::DeprecationWarning -c " +
                                  shlex.quote(module.VERIFY_SCRIPT) + " " +
                                  shlex.quote(self.config["username"]) + " password", secret)
                if result != "verified":
                    raise ValueError("Guest password verification failed")
            value = dict(uuid=self.config["uuid"], fingerprint=fingerprint, verifiedAt=time.time())
            temporary = record.with_suffix(".pending")
            temporary.write_text(json.dumps(value), encoding="utf-8")
            temporary.chmod(0o600)
            os.replace(temporary, record)
        value = json.loads(record.read_text()) if record.exists() else {}
        verified = (value.get("uuid") == self.config["uuid"] and
                    value.get("fingerprint") == fingerprint and
                    0 <= time.time() - value.get("verifiedAt", 0) <= 86400)
        schema = "winvm-credential-handoff/v0" if self.config["platform"] == "windows" else "linuxvm-credential-handoff/v0"
        return dict(schema=schema, ready=verified,
                    verified=verified, mode="password", locatorReady=True)

    def doctor(self):
        protected = (self.state / "protected-base.json").exists()
        states = dict(power="unknown", administration="unavailable", resident="unavailable",
                      desktop="unknown", semantic="unavailable", capture="unavailable",
                      input="unavailable", outer="unavailable")
        checks = []
        operations = []
        try:
            info = self.inspect()
            states["power"] = {"poweroff": "off", "running": "running",
                               "saved": "suspended"}.get(info["VMState"], "unknown")
            checks.append(dict(id="identity", status="pass", summary="Exact VM and disk pins match"))
            states["outer"] = "ready"
            operations = [] if protected else ["up", "shutdown", "force-stop"]
            if states["power"] == "running":
                if self.config["platform"] == "windows":
                    self.powershell("'ready'", timeout=max(15, self.config.get("sshConnectTimeoutSeconds", 5) + 15))
                else:
                    self.ssh("true", timeout=15)
                states["administration"] = "ready"
                status = self.control({"operation": "status"})
                if status.get("accepted") is True:
                    states["resident"] = "ready"
                    data = status.get("data", {})
                    states["desktop"] = "unlocked" if data.get("semanticState") == "ready" or \
                        status.get("desktop") == "Default" else "unknown"
                    for key in ("semantic", "capture", "input"):
                        if data.get(key + "State") == "ready":
                            states[key] = "ready"
                    if self.config["platform"] == "windows":
                        states["desktop"] = "locked" if status.get("sessionLocked") else \
                            "unlocked" if status.get("desktop") == "Default" else "unknown"
                        capabilities = self.control({"operation": "capabilities"})
                        native = any(p.get("id") == "windows-native" and p.get("state") == "native"
                                     for p in capabilities.get("data", {}).get("providers", []))
                        if capabilities.get("accepted") and native and status.get("desktopReady") is not False:
                            for key in ("semantic", "capture", "input"):
                                states[key] = "ready"
                checks.append(dict(id="resident", status="pass" if states["resident"] == "ready" else "warn"))
        except (ValueError, OSError, subprocess.SubprocessError):
            checks.append(dict(id="readiness", status="fail", summary="A pinned identity or guest route is unavailable"))
        ready = not protected and states["desktop"] == "unlocked" and all(states[name] == "ready" for name in
                    ("administration", "resident", "semantic", "capture", "input"))
        value = dict(schema="machine-control-doctor/v0", ready=ready,
                     target=dict(platform=self.config["platform"], profile=self.config["profile"], kind="desktop"),
                     states=states, checks=checks, lifecycleOperations=operations,
                     extensions=dict(provider="virtualbox-windows", transport="pinned_loopback_ssh",
                                     experimental=True, role="ready-base" if protected
                                     else self.config["role"],
                                     shutdownSchedulerAssist=dict(
                                         enabled=bool(self.config.get("shutdownRescheduleAfterSeconds", 0)),
                                         afterSeconds=self.config.get("shutdownRescheduleAfterSeconds", 0),
                                         requiresDisruptiveClaim=True, route="outer_lifecycle",
                                         hostInterference="none"),
                                     lifecycle=dict(suspend=dict(availability="unavailable", source="provider",
                                                                reasons=["Saved-state recovery is not qualified"]),
                                                    defaultDownAction="guest-shutdown")))
        return value

    def dispatch(self, command, arguments):
        if command == "doctor" and arguments in ([], ["--json"]):
            value = self.doctor(); print(json.dumps(value)); return 0 if value["ready"] else 1
        if command.startswith("claim-"):
            operation = command[6:]
            if operation not in {"capabilities", "status", "acquire", "check", "renew", "release"}:
                raise ValueError("Unsupported claim operation")
            forwarded = [arg for arg in arguments if arg != "--json"]
            if any(arg.split("=", 1)[0] in {"--provider", "--resource-id", "--state-dir"} for arg in forwarded):
                raise ValueError("Claim identity overrides are prohibited")
            if operation not in {"capabilities", "status", "release"}:
                self.inspect()
            result = self.claim(operation, forwarded)
            print(result.stdout.strip()); return result.returncode
        self.require_claim()
        # Serialize same-claim callers as well as exclusive-claim owners.
        directory = claims.state_directory(str(self.state / "operation"))
        with claims.store_lock(directory):
            self.require_claim()
            info = self.inspect()
            images = Images(self)
            if images.protected() and not (command in {"status", "factory-stages", "base-verify"} or
                                           command == "credential" and arguments == ["status", "--json"]):
                raise ValueError("Protected ready base refuses ordinary mutation; derive a candidate")
            if command == "qualify" and arguments == ["--json"]:
                print(json.dumps(images.qualify(info))); return 0
            if command == "promote-base" and arguments == ["--json"]:
                self.require_claim(disruptive=True)
                print(json.dumps(images.promote(info))); return 0
            if command == "base-verify" and arguments == ["--json"]:
                print(json.dumps(images.verify(info))); return 0
            if command == "status" and not arguments:
                print({"poweroff": "off", "saved": "suspended"}.get(info["VMState"], info["VMState"]))
                return 0
            if command == "screenshot" and len(arguments) == 1:
                self.require_claim(disruptive=True)
                output = Path(arguments[0])
                if not output.is_absolute() or output.exists():
                    raise ValueError("A new absolute capture destination is required")
                self.vbox("controlvm", self.config["uuid"], "screenshotpng", output)
                print(output); return 0
            if command == "acpi-shutdown" and not arguments:
                self.require_claim(disruptive=True)
                if info["VMState"] != "running":
                    raise ValueError("ACPI recovery requires a running guest")
                images.invalidate(history=True)
                self.vbox("controlvm", self.config["uuid"], "acpipowerbutton")
                print(json.dumps(dict(delivered=True, effect="unconfirmed")))
                return 0
            if command == "recovery-key":
                self.require_claim(disruptive=True)
                keys = {"enter": ["1c", "9c"], "tab": ["0f", "8f"],
                        "escape": ["01", "81"]}
                if info["VMState"] != "running" or len(arguments) != 1 or arguments[0] not in keys:
                    raise ValueError("A running recovery target and supported key are required")
                images.invalidate(history=True)
                self.vbox("controlvm", self.config["uuid"], "keyboardputscancode", *keys[arguments[0]])
                print(json.dumps(dict(delivered=True, effect="unconfirmed", route="outer_recovery",
                                      hostInterference="none")))
                return 0
            if command == "candidate-hardware":
                self.require_claim(disruptive=True)
                if self.config["role"] != "candidate" or info["VMState"] != "poweroff":
                    raise ValueError("Hardware experiments require a stopped candidate")
                parser = argparse.ArgumentParser(allow_abbrev=False)
                parser.add_argument("--cpus", type=int, choices=range(1, 5))
                parser.add_argument("--x2apic", choices=("on", "off"))
                parser.add_argument("--rtc-use-utc", choices=("on", "off"))
                parser.add_argument("--paravirt-provider", choices=("none", "default", "hyperv"))
                parser.add_argument("--serial-log")
                options = parser.parse_args(arguments)
                changes = []
                if options.cpus is not None:
                    changes += ["--cpus", str(options.cpus)]
                if options.x2apic is not None:
                    changes += ["--x86-x2apic", options.x2apic, "--apic", "on"]
                if options.rtc_use_utc is not None:
                    changes += ["--rtc-use-utc", options.rtc_use_utc]
                if options.paravirt_provider is not None:
                    changes += ["--paravirt-provider", options.paravirt_provider]
                if options.serial_log is not None:
                    serial = Path(options.serial_log)
                    if not serial.is_absolute() or serial.exists() or not serial.parent.is_dir():
                        raise ValueError("A new absolute private serial log path is required")
                    changes += ["--uart1", "0x3f8", "4", "--uart-mode1", "file", str(serial)]
                if not changes:
                    raise ValueError("An explicit candidate hardware change is required")
                images.invalidate(history=True)
                self.vbox("modifyvm", self.config["uuid"], *changes)
                actual = self.inspect()
                if options.cpus is not None and actual.get("cpus") != str(options.cpus):
                    raise ValueError("CPU configuration readback failed")
                if options.x2apic is not None and actual.get("x2apic") != options.x2apic:
                    raise ValueError("APIC configuration readback failed")
                if options.rtc_use_utc is not None and actual.get("rtcuseutc") != options.rtc_use_utc:
                    raise ValueError("RTC configuration readback failed")
                if options.paravirt_provider is not None and actual.get("paravirtprovider") != options.paravirt_provider:
                    raise ValueError("Paravirtualization configuration readback failed")
                return 0
            if command == "credential" and arguments in (["verify", "--json"], ["status", "--json"]):
                result = self.credential(arguments[0] == "verify")
                print(json.dumps(result)); return 0 if result["ready"] else 1
            if command == "login" and not arguments and self.config["platform"] == "windows":
                result = self.login()
                print(json.dumps(result)); return 0 if result.get("accepted") else 1
            if command == "unlock" and not arguments and self.config["platform"] == "windows":
                instance = self.config.get("unlockInstance", "")
                if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", instance):
                    raise ValueError("Explicit installed unlock instance required")
                for key in ("unlockGrantFile", "unlockKeyFile", "credentialFile"):
                    path = Path(self.config.get(key, ""))
                    if not path.is_absolute() or not path.is_file():
                        raise ValueError("Private unlock locators are unavailable")
                environment = os.environ.copy()
                if self.config.get("opensslDirectory"):
                    directory = Path(self.config["opensslDirectory"])
                    if not directory.is_absolute() or not (directory / "openssl.exe").is_file():
                        raise ValueError("Native OpenSSL locator is unavailable")
                    environment["PATH"] = str(directory) + os.pathsep + environment.get("PATH", "")
                carrier = "& 'C:\\Program Files\\MachineControlUnlock\\" + instance + \
                    "\\machine-control-windows.exe' unlock --relay --instance " + instance
                # The existing controller reads the canonical secret only after
                # signed authorization and native credential-field discovery.
                result = subprocess.run([sys.executable, str(ROOT / "release/unlock-controller.py"),
                    "unlock", "--instance", instance, "--grant", self.config["unlockGrantFile"],
                    "--key", self.config["unlockKeyFile"], "--secret-file", self.config["credentialFile"],
                    "--", *self.ssh_arguments(carrier)], env=environment,
                    capture_output=True, text=True, encoding="utf-8", timeout=100)
                print(result.stdout.strip())
                return result.returncode
            if command == "factory-stages" and arguments == ["--json"]:
                observed = self.doctor()
                promotion = "waiting"
                if images.protected():
                    try:
                        promotion = "complete" if images.verify(info, hashes=False)["verified"] else "blocked"
                    except (ValueError, KeyError, OSError):
                        promotion = "blocked"
                try:
                    credential = self.credential()["ready"]
                except (ValueError, OSError):
                    credential = False
                stages = [dict(name="identity", state="complete"),
                          dict(name="power", state="complete" if info["VMState"] == "running" else "waiting"),
                          dict(name="transport", state="complete" if observed["states"]["administration"] == "ready" else "waiting"),
                          dict(name="resident", state="complete" if observed["ready"] else "waiting"),
                          dict(name="credential-handoff", state="complete" if credential else "action_required"),
                          dict(name="media", state="complete" if info.get("SATA-1-0") == "none" else "action_required"),
                          dict(name="final-stop", state="complete" if info["VMState"] == "poweroff" else "waiting"),
                          dict(name="promotion", state=promotion)]
                schema = "linuxvm-factory-stages/v0" if self.config["platform"] == "linux" else "winvm-factory-stages/v0"
                print(json.dumps(dict(schema=schema, provider="virtualbox-windows", stages=stages,
                                      limitations=["Isolated workspaces are not qualified"])))
                return 0
            if command == "up" and not arguments:
                if info["VMState"] == "poweroff":
                    images.starting()
                    self.vbox("startvm", self.config["uuid"], "--type", "headless")
                elif info["VMState"] != "running":
                    raise ValueError("Unsupported initial power state")
                return 0
            if command == "detach-bootstrap-media" and not arguments:
                if self.config["role"] != "candidate" or info["VMState"] != "poweroff":
                    raise ValueError("Bootstrap detachment requires a stopped candidate")
                expected = self.config.get("bootstrapMedia")
                if not expected or not Path(expected).is_absolute() or \
                        Path(info.get("SATA-1-0", "")).resolve() != Path(expected).resolve():
                    raise ValueError("Bootstrap media identity mismatch")
                if not self.credential()["ready"]:
                    raise ValueError("Verified credential handoff required")
                self.vbox("storageattach", self.config["uuid"], "--storagectl", "SATA",
                          "--port", "1", "--device", "0", "--type", "dvddrive", "--medium", "none")
                if self.inspect().get("SATA-1-0") != "none":
                    raise ValueError("Bootstrap detachment unconfirmed")
                return 0
            if command in {"shutdown", "force-stop"} and not arguments:
                if info["VMState"] == "poweroff":
                    return 0
                assist = self.config.get("shutdownRescheduleAfterSeconds", 0) if command == "shutdown" else 0
                if assist:
                    self.require_claim(disruptive=True)
                if command == "force-stop":
                    self.require_claim(disruptive=True)
                    images.invalidate(history=True)
                    self.vbox("controlvm", self.config["uuid"], "poweroff")
                elif self.config["platform"] == "windows":
                    self.powershell("shutdown.exe /s /t 0")
                else:
                    self.ssh("sudo systemd-run --on-active=2 /usr/bin/systemctl poweroff")
                # Windows can finish servicing/session teardown long after SSH
                # exits. A short timeout is not evidence of a frozen guest.
                start = time.monotonic()
                deadline = start + (900 if self.config["platform"] == "windows" else 120)
                assisted = False
                while (now := time.monotonic()) < deadline:
                    self.require_claim()
                    stopped = self.inspect()
                    if stopped["VMState"] == "poweroff":
                        if command == "shutdown":
                            images.stopped(stopped, now - start, scheduler_assisted=assisted)
                        return 0
                    if assist and not assisted and now - start >= assist:
                        self.require_claim(disruptive=True)
                        # Explicit private compatibility profile, not a power
                        # cut. Always restore scheduling after our own pause.
                        try:
                            self.vbox("controlvm", self.config["uuid"], "pause")
                        finally:
                            if self.inspect()["VMState"] == "paused":
                                self.vbox("controlvm", self.config["uuid"], "resume")
                        assisted = True
                    time.sleep(2)
                raise ValueError("Shutdown unconfirmed; no automatic force-stop")
            if command in {"control", "control-local"} and len(arguments) == 1:
                value = self.control(json.loads(arguments[0])); print(json.dumps(value))
                return 0 if value.get("accepted") else 1
            if command == "ps" and len(arguments) == 1 and self.config["platform"] == "windows":
                print(self.powershell(arguments[0], timeout=600)); return 0
            if command == "push" and len(arguments) == 2:
                source, destination = arguments
                if self.config["platform"] == "linux":
                    if not destination.startswith("/"):
                        raise ValueError("An absolute guest destination is required")
                    self.ssh("sudo tee " + shlex.quote(destination) + " >/dev/null", Path(source).read_bytes())
                else:
                    if not re.match(r"^[A-Za-z]:[\\/]", destination) or \
                            any(c in destination for c in "\r\n\0"):
                        raise ValueError("An absolute guest destination is required")
                    c = self.config
                    executable = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/OpenSSH/scp.exe"
                    result = subprocess.run([str(executable), "-F", "NUL", "-P", str(c["sshPort"]),
                        "-i", c["sshKey"], "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
                        "-o", "StrictHostKeyChecking=yes", "-o",
                        "ConnectTimeout=" + str(self.config.get("sshConnectTimeoutSeconds", 5)),
                        "-o", "UserKnownHostsFile=" + c["knownHosts"], str(Path(source).resolve()),
                        c["username"] + "@127.0.0.1:" + destination.replace("\\", "/")],
                        capture_output=True, timeout=600)
                    if result.returncode:
                        raise ValueError("Pinned guest SFTP transfer failed")
                return 0
            if command in {"artifact", "artifact-fetch"} and len(arguments) == 2:
                identifier, destination = arguments
                if self.config["platform"] == "linux":
                    if str(uuid.UUID(identifier)) != identifier:
                        raise ValueError("Resident artifact ID required")
                    encoded = self.ssh("base64 -w0 ~/.cache/linuxvm-testbed/artifacts/" + identifier + ".png")
                else:
                    if not re.fullmatch(r"[a-f0-9]{32}", identifier):
                        raise ValueError("Resident artifact ID required")
                    encoded = self.powershell("[Convert]::ToBase64String([IO.File]::ReadAllBytes("
                                              "'C:\\ProgramData\\MachineControl\\artifacts\\" + identifier + ".png'))")
                data = base64.b64decode(encoded, validate=True)
                if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("Resident artifact is not a PNG")
                with Path(destination).open("xb") as stream:
                    stream.write(data)
                print(destination); return 0
            if command == "exec" and self.config["platform"] == "linux":
                if arguments and arguments[0] == "--":
                    arguments = arguments[1:]
                if not arguments:
                    raise ValueError("Guest command required")
                print(self.ssh(shlex.join(arguments))); return 0
            raise ValueError("Operation is not qualified by this experimental adapter")


def main(arguments=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        arguments = sys.argv[1:] if arguments is None else arguments
        if sys.platform != "win32" or not arguments:
            raise ValueError("A Windows controller and operation are required")
        config = load_config(os.environ["MACHINE_CONTROL_VBOX_CONFIG"])
        return Adapter(config).dispatch(arguments[0], arguments[1:])
    except (ValueError, KeyError, OSError, subprocess.SubprocessError, claims.ClaimError) as error:
        print("VirtualBox adapter refused: " + type(error).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
