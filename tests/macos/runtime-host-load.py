#!/usr/bin/env python3
"""Bounded read-only load/recovery on an isolated signed Mac host candidate.

The caller owns host doctor/claim/release. No grants, input, helper setup,
installed-app replacement, or canonical preference writes occur here.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile
import threading
import time


def jxa(source):
    return subprocess.check_output(["/usr/bin/osascript", "-l", "JavaScript", "-e", source], text=True).strip()


def fingerprint(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def resources(pid):
    rss = int(subprocess.check_output(["/bin/ps", "-o", "rss=", "-p", str(pid)], text=True).strip())
    files = subprocess.check_output(["/usr/sbin/lsof", "-a", "-p", str(pid), "-F", "f"], text=True)
    return {"rssKiB": rss, "fds": sum(bool(re.fullmatch(r"f\d+", line)) for line in files.splitlines())}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, type=Path)
    parser.add_argument("--claim", required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--seconds", type=int, default=90)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    options = parser.parse_args()
    if not 30 <= options.seconds <= 300 or not 1 <= options.workers <= 16:
        parser.error("Use 30–300 seconds and 1–16 workers")
    app = options.app.resolve()
    binary = app / "Contents/MacOS/macui"
    installed_app = Path.home() / "Applications/Machine Control.app"
    if app == installed_app.resolve() or app == Path("/Applications/Machine Control.app").resolve():
        parser.error("Supply a separate candidate, not the installed app")
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    options.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(options.evidence_dir, 0o700)
    root = Path(tempfile.mkdtemp(prefix="mc-host-load-", dir="/tmp"))
    endpoint = root / "control.sock"
    paths = [installed_app / "Contents/MacOS/macui",
             Path("/Applications/Machine Control.app/Contents/MacOS/macui"),
             Path("/Library/Preferences/org.machine-control.unlock.plist"),
             Path("/Library/Application Support/MachineControl/policy.json"),
             Path.home() / "Library/Application Support/MachineControl/presentation.json"]
    before = [fingerprint(path) for path in paths]
    initial_pid = int(jxa('ObjC.import("AppKit"); Number($.NSWorkspace.sharedWorkspace.frontmostApplication.processIdentifier);'))
    cli = app / "Contents/Resources/mc-cli/commands/machine-control"
    common = [str(cli)]
    if options.registry:
        common += ["--registry", str(options.registry.resolve())]
    common += ["--target", "host", "--claim", options.claim]
    stop = threading.Event()
    lock = threading.Lock()
    latencies = []
    counts = {}
    errors = []
    process = None
    installed_pid = None

    def call(operation):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
            stream.settimeout(5)
            stream.connect(str(endpoint))
            stream.sendall(json.dumps({"operation": operation, "claimId": options.claim}).encode() + b"\n")
            data = bytearray()
            while not data.endswith(b"\n"):
                chunk = stream.recv(65536)
                if not chunk:
                    raise AssertionError("Candidate closed a discovery request without a reply")
                data.extend(chunk)
                if len(data) >= 2 * 1024 * 1024:
                    raise AssertionError("Unexpected discovery response size")
            return json.loads(data)

    def status():
        for _ in range(100):
            value = call("status")
            if value.get("accepted"):
                data = value["data"]
                assert data["processId"] == process.pid
                assert data["deployment"]["grant"] is None
                assert data["deployment"]["policy"]["grantMode"] == "approval"
                return data
            assert value.get("errorCode") in {"native_provider_busy", "control_generation_changed"}, value
            time.sleep(0.02)
        raise AssertionError("Status did not recover")

    def worker(index):
        operations = ["grant.status", "status", "desktop.delegation.status", "grant.status"]
        iteration = index
        while not stop.is_set():
            operation = operations[iteration % len(operations)]
            started = time.monotonic()
            try:
                value = call(operation)
                code = "accepted" if value.get("accepted") else value.get("errorCode")
                assert code in {"accepted", "native_provider_busy", "control_generation_changed"}, value
                if value.get("accepted") and operation == "status":
                    assert value["data"]["processId"] == process.pid
                    assert value["data"]["deployment"]["grant"] is None
                with lock:
                    latencies.append(time.monotonic() - started)
                    counts[code] = counts.get(code, 0) + 1
            except Exception as error:
                with lock:
                    errors.append(str(error))
                stop.set()
                return
            iteration += 1
            stop.wait(0.025)

    try:
        installed = json.loads(subprocess.check_output(common + ["desktop", "raw", '{"operation":"status"}'], text=True))
        assert installed["accepted"]
        installed_pid = installed["data"]["processId"]
        subprocess.run([str(cli), "presentation", "set", "appliance", "--socket", str(endpoint)],
                       check=True, stdout=subprocess.DEVNULL)
        with (options.evidence_dir / "candidate.log").open("w") as log:
            process = subprocess.Popen([str(binary), "serve", str(endpoint), "--presentation", "minimal"],
                                       stdout=log, stderr=log)
        for _ in range(100):
            if endpoint.exists():
                break
            assert process.poll() is None, "Candidate exited at startup"
            time.sleep(0.1)
        initial = status()
        assert initial["presentation"]["settingsWebViews"] == 0
        assert initial["presentation"]["profile"] == "minimal"
        env = {**os.environ, "MACHINE_CONTROL_HOST_SOCKET": str(endpoint)}
        # Exercise packaged/common transport before the direct native load.
        value = json.loads(subprocess.check_output(common + ["desktop", "raw", '{"operation":"status"}'], env=env, text=True))
        assert value["accepted"] and value["data"]["processId"] == process.pid
        # Saturate incomplete public handshakes; Settings has an independent
        # same-user endpoint and must recover while discovery is overloaded.
        handshake_baseline = resources(process.pid)
        stalled = []
        handshake_refusals = 0
        try:
            for _ in range(96):
                peer = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                peer.settimeout(2)
                try:
                    peer.connect(str(endpoint))
                except (ConnectionRefusedError, TimeoutError):
                    peer.close()
                    assert process.poll() is None, "Candidate exited during handshake overload"
                    handshake_refusals += 1
                    time.sleep(0.01)
                    continue
                stalled.append(peer)
            time.sleep(0.2)
            handshake_peak = resources(process.pid)
            assert handshake_peak["fds"] <= handshake_baseline["fds"] + 64 + 16, (handshake_baseline, handshake_peak)
            started = time.monotonic()
            subprocess.run([str(binary), "serve", str(endpoint), "--settings"], check=True, timeout=5)
            handshake_recovery = time.monotonic() - started
            assert handshake_recovery < 2
        finally:
            for peer in stalled:
                peer.close()
        assert status()["presentation"]["settingsWebViews"] == 1
        recovery = []
        measurements = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=options.workers) as executor:
            tasks = [executor.submit(worker, index) for index in range(options.workers)]
            try:
                time.sleep(2)
                for _ in range(5):
                    started = time.monotonic()
                    subprocess.run([str(binary), "serve", str(endpoint), "--settings"], check=True, timeout=5)
                    recovery.append(time.monotonic() - started)
                    assert status()["presentation"]["settingsWebViews"] == 1
                    time.sleep(0.1)
                time.sleep(3)  # Establish a baseline after lazy WebView startup.
                sample = options.evidence_dir / "sample.txt"
                subprocess.run(["/usr/bin/sample", str(process.pid), "2", "-file", str(sample)],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                sampled = sample.read_text()
                match = re.search(r"Thread_\d+[^\n]*(?:com\.apple\.main-thread|: main)", sampled)
                assert match, "Main-thread sample missing"
                end = sampled.find("Thread_", match.end())
                main_thread = sampled[match.start():end if end >= 0 else len(sampled)]
                assert "ResidentService.unlockStatus" not in main_thread and "readSocket" not in main_thread
                assert "DesktopJournal.append" not in main_thread, "Discovery unexpectedly wrote audit records"
                until = time.monotonic() + options.seconds
                while time.monotonic() < until:
                    assert not errors, errors
                    measurements.append(resources(process.pid))
                    stop.wait(min(15, max(0, until - time.monotonic())))
                assert not errors, errors
            finally:
                stop.set()
                for task in tasks:
                    task.result(timeout=8)
        final = status()
        assert final["presentation"]["settingsWebViews"] == 1
        assert final["presentation"]["profile"] == "minimal"
        saved = json.loads(subprocess.check_output([str(cli), "presentation", "status", "--socket", str(endpoint)], text=True))
        assert saved["profile"] == "appliance"
        settled = resources(process.pid)
        assert settled["fds"] <= measurements[0]["fds"] + 16, (measurements, settled)
        assert settled["rssKiB"] <= measurements[0]["rssKiB"] + 64 * 1024, (measurements, settled)
        latencies.sort()
        assert latencies and max(recovery) < 2
        result = {"schema":"machine-control-mac-host-load/v1", "seconds":options.seconds,
                  "workers":options.workers, "requests":len(latencies), "outcomes":counts,
                  "requestP99Ms":round(latencies[int((len(latencies) - 1) * 0.99)] * 1000, 1),
                  "requestMaxMs":round(latencies[-1] * 1000, 1),
                  "settingsRecoveryMs":[round(value * 1000, 1) for value in recovery],
                  "handshakeAttempts":96, "connectedHandshakePeers":len(stalled),
                  "handshakeConnectRefusals":handshake_refusals, "handshakeBaseline":handshake_baseline,
                  "handshakePeak":handshake_peak, "handshakeSettingsRecoveryMs":round(handshake_recovery * 1000, 1),
                  "resourceSamples":measurements, "settledResources":settled,
                  "noAccessGrant":True, "mainThreadSampleClear":True,
                  "sameRuntimeRecovery":True, "canonicalFingerprintsUnchanged":before == [fingerprint(path) for path in paths]}
        assert result["canonicalFingerprintsUnchanged"]
        (options.evidence_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
    finally:
        stop.set()
        settings_sockets = []
        if process is not None and process.poll() is None:
            names = subprocess.run(["/usr/sbin/lsof", "-a", "-U", "-p", str(process.pid), "-F", "n"],
                                   capture_output=True, text=True).stdout
            for line in names.splitlines():
                if line.startswith(("n/tmp/mc-settings-", "n/private/tmp/mc-settings-")):
                    path = Path(line[1:])
                    try:
                        info = path.lstat()
                        if stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid():
                            settings_sockets.append((path, info.st_dev, info.st_ino))
                    except FileNotFoundError:
                        pass
            jxa('ObjC.import("AppKit"); $.NSRunningApplication.runningApplicationWithProcessIdentifier(' + str(process.pid) + ').terminate;')
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=10)
        for path, device, inode in settings_sockets:
            try:
                info = path.lstat()
                if (info.st_dev, info.st_ino) == (device, inode):
                    path.unlink()
            except FileNotFoundError:
                pass
        jxa('ObjC.import("AppKit"); var a=$.NSRunningApplication.runningApplicationWithProcessIdentifier(' + str(initial_pid) + '); if(a) a.activateWithOptions(2);')
        assert [fingerprint(path) for path in paths] == before, "Canonical host state changed"
        if installed_pid is not None:
            installed = json.loads(subprocess.check_output(common + ["desktop", "raw", '{"operation":"status"}'], text=True))
            assert installed["accepted"] and installed["data"]["processId"] == installed_pid, "Installed resident replaced"
        # Retain only private evidence; remove this run's isolated preferences.
        import shutil
        shutil.rmtree(root)


if __name__ == "__main__":
    main()
