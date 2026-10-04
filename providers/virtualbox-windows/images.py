"""Private, same-controller qualification receipts and protected base manifests."""
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def write_atomic(path, value):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            os.chmod(temporary, 0o600)
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def hardware(info, scheduler_assist=0, connect_timeout=5):
    keys = ("UUID", "SATA-ImageUUID-0-0", "cpus", "memory", "firmware", "tpm-type",
            "x2apic", "apic", "rtcuseutc", "paravirtprovider", "effparavirtprovider",
            "graphicscontroller", "accelerate3d", "nictype1", "nic1")
    return hashlib.sha256(json.dumps({**{k: info.get(k) for k in keys},
                                     "shutdownSchedulerAssist": scheduler_assist,
                                     "sshConnectTimeoutSeconds": connect_timeout},
                                     sort_keys=True).encode()).hexdigest()


def file_stamp(path):
    stat = Path(path).stat()
    return dict(size=stat.st_size, modifiedNs=stat.st_mtime_ns)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


class Images:
    def __init__(self, adapter):
        self.adapter = adapter
        self.hardware = lambda info: hardware(info, adapter.config.get("shutdownRescheduleAfterSeconds", 0),
                                             adapter.config.get("sshConnectTimeoutSeconds", 5))
        self.directory = adapter.state
        self.directory.mkdir(parents=True, exist_ok=True)
        self.qualification = self.directory / "qualification.json"
        self.history = self.directory / "clean-lifecycle.json"
        self.manifest = self.directory / "protected-base.json"
        self.pending = self.directory / "unqualified-boot.json"

    def protected(self):
        # A malformed manifest also blocks mutation; never silently unprotect.
        return self.manifest.exists()

    def invalidate(self, history=False):
        if self.qualification.exists():
            self.qualification.unlink()
        if history and self.history.exists():
            self.history.unlink()

    def starting(self):
        self.invalidate()
        write_atomic(self.pending, dict(startedAt=time.time()))

    def qualify(self, info):
        a = self.adapter
        if a.config["platform"] != "windows" or info["VMState"] != "running":
            raise ValueError("Windows running qualification required")
        if not a.doctor()["ready"]:
            raise ValueError("Ready resident doctor required")
        facts = json.loads(a.powershell(r"""
$ErrorActionPreference='Stop'
$uac=Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System'
$session=Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager'
$pending=(Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') -or
 (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') -or
 [bool]$session.PendingFileRenameOperations -or
 [bool](Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Updates' -Name UpdateExeVolatile -ErrorAction SilentlyContinue).UpdateExeVolatile
$winlogon=Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
[ordered]@{
 boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
 secureBoot=[bool](Confirm-SecureBootUEFI); tpmReady=[bool](Get-Tpm).TpmReady
 uac=($uac.EnableLUA -eq 1 -and $uac.PromptOnSecureDesktop -eq 1)
 pendingRestart=[bool]$pending
 servicing=[bool](Get-Process TiWorker,TrustedInstaller -ErrorAction SilentlyContinue)
 autoLogin=($winlogon.AutoAdminLogon -eq '1')
 cachedPassword=($winlogon.PSObject.Properties.Name -contains 'DefaultPassword')
} | ConvertTo-Json -Compress
""", timeout=45))
        if not all(facts.get(k) is True for k in ("secureBoot", "tpmReady", "uac")) or \
                any(facts.get(k) is not False for k in
                    ("pendingRestart", "servicing", "autoLogin", "cachedPassword")) or not facts.get("boot"):
            raise ValueError("Security, servicing or unattended credential cleanup is incomplete")
        if any(info.get("SATA-" + str(port) + "-0", "none") != "none" for port in (1, 2, 3)):
            raise ValueError("Detached installation media required")
        if not a.credential(verify=True)["ready"]:
            raise ValueError("Live canonical password verification required")
        a.require_claim()
        fresh = a.inspect()
        if fresh["VMState"] != "running" or self.hardware(fresh) != self.hardware(info):
            raise ValueError("Qualification identity changed")
        value = dict(schema="machine-control-virtualbox-qualification/v0",
                     resource=a.resource, hardware=self.hardware(info), observedAt=time.time(),
                     facts=facts, credentialStamp=file_stamp(a.config["credentialFile"]))
        write_atomic(self.qualification, value)
        return dict(qualified=True, promotionReady=False, checks=facts)

    def stopped(self, info, seconds, scheduler_assisted=False):
        a = self.adapter
        if not self.qualification.exists():
            return
        value = json.loads(self.qualification.read_text(encoding="utf-8"))
        if info["VMState"] != "poweroff" or value.get("resource") != a.resource or \
                value.get("hardware") != self.hardware(info) or time.time() - value["observedAt"] > 1800:
            self.invalidate()
            return
        value.update(stoppedAt=time.time(), shutdownSeconds=seconds,
                     shutdownSchedulerAssist=scheduler_assisted,
                     diskStamp=file_stamp(a.config["disk"]))
        history = json.loads(self.history.read_text(encoding="utf-8")) if self.history.exists() else []
        history = [v for v in history if v["facts"]["boot"] != value["facts"]["boot"]]
        write_atomic(self.history, [*history[-9:], value])
        self.invalidate()
        if self.pending.exists():
            self.pending.unlink()

    def promote(self, info):
        a = self.adapter
        if a.config["role"] != "candidate" or info["VMState"] != "poweroff" or self.protected():
            raise ValueError("Promotion requires an unprotected stopped candidate")
        if self.pending.exists():
            raise ValueError("An unqualified lifecycle transition remains")
        history = json.loads(self.history.read_text(encoding="utf-8")) if self.history.exists() else []
        matches = [v for v in history if v.get("resource") == a.resource and
                   v.get("hardware") == self.hardware(info) and
                   v.get("credentialStamp") == file_stamp(a.config["credentialFile"]) and
                   0 <= time.time() - v.get("stoppedAt", 0) <= 86400]
        if len({v["facts"]["boot"] for v in matches}) < 3:
            raise ValueError("Three qualified distinct boots and completed OS shutdowns required")
        if matches[-1]["diskStamp"] != file_stamp(a.config["disk"]):
            raise ValueError("Disk changed after qualified shutdown")
        paths = [Path(a.config["disk"]), Path(a.config["vmFile"])]
        nvram = Path(a.config["vmFile"]).with_suffix(".nvram")
        if not nvram.is_file():
            raise ValueError("Firmware and TPM state must accompany the base")
        paths.append(nvram)
        files = [dict(path=str(p), stamp=file_stamp(p), sha256=digest(p)) for p in paths]
        a.require_claim(disruptive=True)
        fresh = a.inspect()
        if fresh["VMState"] != "poweroff" or self.hardware(fresh) != self.hardware(info) or \
                matches[-1]["credentialStamp"] != file_stamp(a.config["credentialFile"]) or \
                any(v["stamp"] != file_stamp(v["path"]) for v in files):
            raise ValueError("Base changed while hashing")
        value = dict(schema="machine-control-virtualbox-base/v0", role="ready-base",
                     resource=a.resource, uuid=a.config["uuid"], diskUuid=a.config["diskUuid"],
                     promotedAt=time.time(), hardware=self.hardware(info), files=files,
                     lifecycle=matches, credentialFile=a.config["credentialFile"],
                     credentialStamp=file_stamp(a.config["credentialFile"]),
                     scope="same-controller private appliance", isolatedWorkspaces=False)
        write_atomic(self.manifest, value)
        return dict(promoted=True, role="ready-base", protected=True,
                    qualifiedBoots=len(matches), isolatedWorkspaces=False)

    def verify(self, info, hashes=True):
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        expected = [str(Path(self.adapter.config["disk"])), str(Path(self.adapter.config["vmFile"])),
                    str(Path(self.adapter.config["vmFile"]).with_suffix(".nvram"))]
        if value.get("schema") != "machine-control-virtualbox-base/v0" or \
                [v["path"] for v in value["files"]] != expected or \
                value.get("resource") != self.adapter.resource or value.get("hardware") != self.hardware(info) or \
                info["VMState"] != "poweroff" or value.get("credentialStamp") != file_stamp(
                    self.adapter.config["credentialFile"]):
            raise ValueError("Protected base identity, power or credential changed")
        if any(v["stamp"] != file_stamp(v["path"]) or hashes and v["sha256"] != digest(v["path"])
               for v in value["files"]):
            raise ValueError("Protected base file verification failed")
        self.adapter.require_claim()
        fresh = self.adapter.inspect()
        if fresh["VMState"] != "poweroff" or self.hardware(fresh) != value["hardware"]:
            raise ValueError("Protected base changed during verification")
        return dict(verified=True, role="ready-base", protected=True,
                    qualifiedBoots=len(value["lifecycle"]), isolatedWorkspaces=False)
