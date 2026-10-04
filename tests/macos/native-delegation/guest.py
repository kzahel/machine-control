#!/usr/bin/env python3
"""Dedicated-guest signed delegation acceptance, invoked by run.py.

Operator enrollment/controls use the separate appliance resident's native AX.
No native trust setter or fixture admission is injected into the candidate.
"""

import json, os, pathlib, subprocess, time, socket, urllib.request, urllib.error, signal, sys

root = pathlib.Path(sys.argv[1])
home = pathlib.Path.home()
case = sys.argv[2] if len(sys.argv) > 2 else "ordinary"
assert case in ("ordinary", "boundaries", "provider-exit", "integration-exit")
assert (
    root.is_absolute() and root.resolve().parent == pathlib.Path("/tmp").resolve()
), "Use an isolated guest temporary directory"
assert root.stat().st_mode & 0o077 == 0, "Fixture directory must be private"
assert (
    root / "auth.private.json"
).stat().st_mode & 0o077 == 0, "Credential proof must be private"
for name in ["Machine Control.app", "YepAnywhere.app"]:
    subprocess.run(
        ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(root / name)],
        check=True,
        capture_output=True,
    )
standard = home / "Library/Application Support/MachineControl/control.sock"
upstream = pathlib.Path(str(standard) + ".qa-upstream")
processes = []
broker = None
shifted = False
ya_installed = False
fixture_pid = None
fixture_started = False
policy_changed = False
policy = pathlib.Path("/Library/Application Support/MachineControl/policy.json")
policy_before = policy.read_bytes()
original_socket_inode = standard.stat().st_ino
original_ya_inode = (
    pathlib.Path("/Applications/YepAnywhere.app").stat().st_ino
    if pathlib.Path("/Applications/YepAnywhere.app").exists()
    else None
)
canonical = pathlib.Path("/Applications/YepAnywhere.app")
backup = root / "previous-ya.app"
assert (
    standard.exists() and not upstream.exists()
), "Existing native provider must be ready"
state_before = {
    name: (
        (standard.parent / name).read_bytes()
        if (standard.parent / name).exists()
        else None
    )
    for name in ["operator-consent.json", "desktop-caller-trust.json"]
}


def readjson(path):
    return json.loads(path.read_text())


def waitfile(path, timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if path.exists():
            return readjson(path)
        time.sleep(0.1)
    raise RuntimeError("fixture result timeout")


def command(index, operation):
    (root / f"command-{index}.json").write_text(json.dumps({"operation": operation}))
    return waitfile(root / f"result-{index}.json")


def rpc(path, request):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(15)
        client.connect(str(path))
        client.sendall((json.dumps(request) + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            block = client.recv(65536)
            if not block or len(data) + len(block) > 4 * 1024 * 1024:
                raise RuntimeError(
                    "Native fixture response closed or exceeded its bound"
                )
            data += block
        return json.loads(data)


def fixture():
    value = readjson(home / "Library/Caches/machine-control-fixture/state.json")
    if fixture_pid is not None:
        assert value["pid"] == fixture_pid, "fixture oracle process changed"
    return value


def expect(result, key, value):
    if result.get(key) != value:
        (root / "failure.private.json").write_text(json.dumps(result))
        raise RuntimeError("conformance assertion failed: " + key)


try:
    for pattern in [
        "command-*.json",
        "result-*.json",
        "agent-runtime.json",
        "failure.private.json",
    ]:
        for path in root.glob(pattern):
            path.unlink()
    apps = rpc(standard, {"operation": "applications", "provider": "macos-native"})[
        "data"
    ]["applications"]
    existing = [
        app for app in apps if app.get("bundleId") == "org.machine-control.fixture"
    ]
    fixture_started = not existing
    if fixture_started:
        subprocess.run(
            [
                "/usr/bin/open",
                "-a",
                str(home / "Applications/Machine Control Fixture.app"),
            ],
            check=True,
        )
    end = time.monotonic() + 15
    while time.monotonic() < end:
        apps = rpc(standard, {"operation": "applications", "provider": "macos-native"})[
            "data"
        ]["applications"]
        matching = [
            app for app in apps if app.get("bundleId") == "org.machine-control.fixture"
        ]
        if len(matching) == 1:
            fixture_pid = matching[0]["processId"]
            try:
                fixture()
                break
            except (AssertionError, FileNotFoundError):
                pass
        time.sleep(0.1)
    else:
        raise RuntimeError("fixture did not become independently ready")
    before = fixture()["count"]
    expected_effects = 2
    assert not backup.exists()
    if canonical.exists():
        os.rename(canonical, backup)
    ya_installed = True
    subprocess.run(
        ["/usr/bin/ditto", str(root / "YepAnywhere.app"), str(canonical)], check=True
    )
    os.rename(standard, upstream)
    shifted = True
    policy_changed = True
    subprocess.run(
        ["/usr/bin/sudo", "-n", "/usr/bin/tee", str(policy) + ".qa-new"],
        input=b'{"schema":"machine-control-policy/v0","preset":"workstation"}',
        stdout=subprocess.DEVNULL,
        check=True,
    )
    subprocess.run(
        ["/usr/bin/sudo", "-n", "/bin/chmod", "644", str(policy) + ".qa-new"],
        check=True,
    )
    subprocess.run(
        ["/usr/bin/sudo", "-n", "/bin/mv", str(policy) + ".qa-new", str(policy)],
        check=True,
    )
    broker = subprocess.Popen(
        [
            str(root / "Machine Control.app/Contents/MacOS/macui"),
            "serve",
            str(standard),
        ],
        stdout=open(root / "broker.log", "w"),
        stderr=subprocess.STDOUT,
        text=True,
    )
    processes.append(broker)
    end = time.monotonic() + 15
    while not standard.exists() and time.monotonic() < end:
        time.sleep(0.1)
    candidate_state = rpc(standard, {"operation": "status"})["data"]
    (root / "candidate-state.private.json").write_text(json.dumps(candidate_state))
    assert candidate_state["deployment"]["policy"]["grantMode"] == "approval"
    candidate_pid = candidate_state["processId"]

    def operator_press(label, role="AXButton"):
        end = time.monotonic() + 15
        while time.monotonic() < end:
            snapshot = rpc(
                upstream,
                {
                    "operation": "snapshot",
                    "provider": "macos-native",
                    "target": str(candidate_pid),
                    "projection": "compact",
                    "maxDepth": 30,
                    "maxElements": 600,
                },
            )
            (root / "operator-tree.private.json").write_text(json.dumps(snapshot))
            matches = [
                e
                for e in snapshot.get("data", {}).get("elements", [])
                if e.get("label") == label and e.get("role") == role
            ]
            if len(matches) == 1:
                result = rpc(
                    upstream,
                    {
                        "operation": "action",
                        "provider": "macos-native",
                        "reference": matches[0]["reference"],
                        "action": "press",
                    },
                )
                assert result["accepted"], "native operator press failed"
                return
            time.sleep(0.2)
        raise RuntimeError("operator control not found: " + label)

    rpc(upstream, {"operation": "application.activate", "target": str(candidate_pid)})
    operator_press("Access")
    if rpc(standard, {"operation": "grant.status"})["data"]["availability"]["paused"]:
        operator_press("Resume access")
        time.sleep(0.3)
    profile = rpc(standard, {"operation": "desktop.delegation.status"})
    if profile["data"]["enabled"]:
        operator_press("Allow selected YepAnywhere sessions", "AXCheckBox")
        time.sleep(0.3)
    operator_press("Allow selected YepAnywhere sessions", "AXCheckBox")
    end = time.monotonic() + 20
    while (
        not rpc(standard, {"operation": "desktop.delegation.status"})["data"]["enabled"]
        and time.monotonic() < end
    ):
        time.sleep(0.2)
    assert rpc(standard, {"operation": "desktop.delegation.status"})["data"][
        "enabled"
    ], "native enrollment did not enable trust"
    print("PASS full signed MC native operator enrollment", flush=True)
    # Operator profile is isolated. Real AuthService persisted a credentialed
    # account/session before launch; the cookie remains inside this private runner.
    test_socket = socket.socket()
    test_socket.bind(("127.0.0.1", 0))
    port = test_socket.getsockname()[1]
    test_socket.close()
    (root / "data/config.json").write_text(
        json.dumps(
            {
                "port": port,
                "setup_complete": True,
                "startup_view": "tray_only",
                "agents": [],
            }
        )
    )
    mc = root / "Machine Control.app"
    ya = canonical
    signature = subprocess.run(
        ["/usr/bin/codesign", "-dv", str(mc)], capture_output=True, text=True
    )
    team = next(
        line.split("=", 1)[1]
        for line in signature.stderr.splitlines()
        if line.startswith("TeamIdentifier=")
    )
    env = dict(
        os.environ,
        YEP_DESKTOP_TEST_MODE="1",
        YEP_DESKTOP_TEST_DATA_DIR=str(root / "data"),
        YEP_DESKTOP_CODEX_CLI_PATH=str(root / "codex-fixture.py"),
        YEP_MC_APP=str(mc),
        YEP_MC_TEAM_ID=team,
    )
    native = subprocess.Popen(
        [str(ya / "Contents/MacOS/yep-anywhere-desktop")],
        env=env,
        stdout=open(root / "ya.log", "w"),
        stderr=subprocess.STDOUT,
    )
    processes.append(native)
    base = f"http://127.0.0.1:{port}"
    end = time.monotonic() + 60
    while time.monotonic() < end:
        try:
            if urllib.request.urlopen(base + "/health", timeout=1).status == 200:
                break
        except Exception:
            time.sleep(0.2)
    else:
        raise RuntimeError("signed YA server readiness timeout")
    auth = readjson(root / "auth.private.json")
    request = urllib.request.Request(
        base + "/api/sessions",
        data=json.dumps(
            {
                "message": "Native delegation conformance fixture",
                "provider": "codex",
                "mode": "bypassPermissions",
                "model": "gpt-6",
                "machineControl": True,
            }
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Yep-Anywhere": "true",
            "Cookie": "yep-anywhere-session=" + auth["cookie"],
        },
        method="POST",
    )
    try:
        response = json.load(urllib.request.urlopen(request, timeout=45))
    except urllib.error.HTTPError as error:
        (root / "launch-error.private.json").write_bytes(error.read())
        raise RuntimeError("authenticated session launch refused: " + str(error.code))
    (root / "launch.private.json").write_text(json.dumps(response))
    runtime = waitfile(root / "agent-runtime.json")
    assert runtime["delegated"] is True, "launch did not select native delegation"
    expect(command(1, "open"), "state", "active")
    expect(command(2, "effect"), "accepted", True)
    end = time.monotonic() + 5
    while fixture()["count"] == before and time.monotonic() < end:
        time.sleep(0.1)
    assert (
        fixture()["count"] == before + 1
    ), "independent native effect differs from one"
    print(
        "PASS signed YA credentialed launch registered live fixture provider; native AX effect delta=1",
        flush=True,
    )
    # An unrelated process knows the public locator but is not the live launch.
    proxy = pathlib.Path(runtime["proxy"])
    outsider = subprocess.run(
        [str(mc / "Contents/MacOS/macui"), "delegated-channel", str(proxy)],
        input=(json.dumps({"operation": "control.open"}) + "\n").encode(),
        capture_output=True,
        timeout=15,
    )
    assert (
        outsider.returncode != 0 or not outsider.stdout
    ), "unrelated process forwarded a frame"
    assert fixture()["count"] == before + 1
    print("PASS unrelated same-user native CLI refused without an effect", flush=True)
    operator_press("Pause access")
    time.sleep(0.3)
    expect(command(3, "effect"), "accepted", False)
    expect(command(4, "status"), "state", "paused")
    assert (
        rpc(
            standard, {"operation": "desktop.delegation.status", "requestId": "paused"}
        )["data"]["enabled"]
        is True
    )
    operator_press("Resume access")
    time.sleep(0.3)
    expect(command(5, "accept"), "state", "active")
    expect(command(6, "effect"), "accepted", True)
    end = time.monotonic() + 5
    while fixture()["count"] < before + expected_effects and time.monotonic() < end:
        time.sleep(0.1)
    assert fixture()["count"] == before + expected_effects
    print(
        "PASS Pause retains trust; fresh Resume permits exactly one new effect",
        flush=True,
    )
    extra_commands = 0
    if case in ("provider-exit", "integration-exit"):
        old_runtime = runtime
        rows = subprocess.run(
            ["/bin/ps", "-axo", "pid=,ppid=,command="], capture_output=True, text=True
        ).stdout.splitlines()
        old_descendants = []
        known = {native.pid}
        for _ in range(10):
            for row in rows:
                columns = row.strip().split(None, 2)
                if (
                    len(columns) == 3
                    and int(columns[1]) in known
                    and int(columns[0]) not in known
                ):
                    known.add(int(columns[0]))
                    old_descendants.append((int(columns[0]), columns[2]))
        if case == "provider-exit":
            identity = subprocess.run(
                ["/bin/ps", "-p", str(runtime["pid"]), "-o", "command="],
                capture_output=True,
                text=True,
            ).stdout
            assert str(root / "codex-fixture.py") in identity
            os.kill(runtime["pid"], signal.SIGTERM)
        else:
            native.kill()  # abrupt native integration loss, not graceful cleanup
            native.wait(timeout=5)
        end = time.monotonic() + 8
        while (
            rpc(standard, {"operation": "status"})["data"]["admission"]["active"]
            and time.monotonic() < end
        ):
            time.sleep(0.1)
        assert (
            rpc(standard, {"operation": "status"})["data"]["admission"]["active"] == 0
        )
        assert rpc(standard, {"operation": "desktop.delegation.status"})["data"][
            "enabled"
        ]
        assert fixture()["count"] == before + expected_effects
        if case == "integration-exit":
            # Reap only the old native process's exact captured descendants.
            for pid, identity in reversed(old_descendants):
                current = subprocess.run(
                    ["/bin/ps", "-p", str(pid), "-o", "command="],
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                if current == identity:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
            end = time.monotonic() + 5
            for pid, identity in reversed(old_descendants):
                while time.monotonic() < end:
                    current = subprocess.run(
                        ["/bin/ps", "-p", str(pid), "-o", "command="],
                        capture_output=True,
                        text=True,
                    ).stdout.strip()
                    if current != identity:
                        break
                    time.sleep(0.1)
                if current == identity:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            native = subprocess.Popen(
                [str(ya / "Contents/MacOS/yep-anywhere-desktop")],
                env=env,
                stdout=open(root / "ya-restart.log", "w"),
                stderr=subprocess.STDOUT,
            )
            processes.append(native)
            end = time.monotonic() + 60
            while time.monotonic() < end:
                try:
                    if (
                        urllib.request.urlopen(base + "/health", timeout=1).status
                        == 200
                    ):
                        break
                except Exception:
                    time.sleep(0.2)
            else:
                raise RuntimeError("Signed integration restart readiness timeout")
        for pattern in ("command-*.json", "result-*.json", "agent-runtime.json"):
            for path in root.glob(pattern):
                path.unlink()
        # Authentication is fresh in the restarted server; no origin object or
        # runtime registration is restored from the previous launch.
        json.load(urllib.request.urlopen(request, timeout=45))
        runtime = waitfile(root / "agent-runtime.json")
        assert runtime["delegated"] and runtime["pid"] != old_runtime["pid"]
        expect(command(1, "open"), "state", "active")
        expect(command(2, "effect"), "accepted", True)
        expected_effects += 1
        end = time.monotonic() + 5
        while fixture()["count"] < before + expected_effects and time.monotonic() < end:
            time.sleep(0.1)
        assert fixture()["count"] == before + expected_effects
        extra_commands = -4
        print(
            "PASS "
            + case
            + " releases ownership and retains trust; fresh authenticated launch has one new effect",
            flush=True,
        )
    if case == "boundaries":
        expect(command(7, "forged-attribution"), "accepted", False)
        expect(command(8, "close"), "accepted", True)
        pending = command(9, "open-prepared-pending")
        expect(pending, "state", "waiting_for_approval")
        assert fixture()["count"] == before + expected_effects
        # A publisher-signed interpreter still cannot authenticate native YA.
        program = """const {createConnection}=require('node:net');
const socket=createConnection({path:process.argv[1]});
const timer=setTimeout(()=>{socket.destroy();process.exit(2)},12000);
socket.on('connect',()=>socket.write(process.argv[2]+'\\n'));
socket.on('data',data=>{process.stdout.write(data);clearTimeout(timer);socket.end()});
socket.on('error',()=>{clearTimeout(timer);process.exit(3)});
socket.on('end',()=>{clearTimeout(timer)});
"""
        frame = {
            "operation": "control.open",
            "requestId": "signed-interpreter-negative",
            "schema": "machine-control-admission/v1",
            "reason": "Negative boundary fixture",
            "scopes": ["observe", "control"],
            "durationSeconds": 60,
            "waitSeconds": 60,
            "desktopDelegation": {
                "schema": "machine-control-desktop-delegation/v1",
                "sessionId": "forged-label",
                "sessionGeneration": "00000000-0000-0000-0000-000000000001",
            },
        }
        negative = subprocess.run(
            [
                str(ya / "Contents/MacOS/bun"),
                "-e",
                program,
                str(standard),
                json.dumps(frame),
            ],
            capture_output=True,
            timeout=15,
        )
        assert negative.stdout, "Signed interpreter refusal was not observed"
        assert json.loads(negative.stdout)["accepted"] is False
        assert fixture()["count"] == before + expected_effects
        operator_press("Enable access")
        refusal = command(10, "accept")
        expect(refusal, "accepted", False)
        expect(refusal, "errorCode", "locked_use_disabled")
        assert fixture()["count"] == before + expected_effects
        assert rpc(standard, {"operation": "desktop.delegation.status"})["data"][
            "enabled"
        ]
        expect(command(11, "close"), "accepted", True)
        expect(command(12, "open"), "state", "active")
        expect(command(13, "protected-dispatch"), "accepted", False)
        assert fixture()["count"] == before + expected_effects
        extra_commands = 7
        print(
            "PASS forged attribution and signed interpreter refusal; separate consent/helper and protected-operation gates",
            flush=True,
        )
    operator_press("Stop access")
    time.sleep(0.3)
    expect(command(7 + extra_commands, "effect"), "accepted", False)
    assert (
        rpc(
            standard, {"operation": "desktop.delegation.status", "requestId": "stopped"}
        )["data"]["enabled"]
        is False
    )
    result = command(8 + extra_commands, "open")
    expect(result, "open", False)
    expect(result, "errorCode", "desktop_trust_not_enabled")
    assert fixture()["count"] == before + expected_effects
    print("PASS Stop fences current work and fresh delegated reconnect", flush=True)
    # A new resident runtime must not restore live ownership or undo Stop.
    broker.terminate()
    broker.wait(timeout=15)
    if standard.exists():
        standard.unlink()
    broker = subprocess.Popen(
        [str(mc / "Contents/MacOS/macui"), "serve", str(standard)],
        stdout=open(root / "broker-restart.log", "w"),
        stderr=subprocess.STDOUT,
    )
    processes.insert(0, broker)
    end = time.monotonic() + 20
    while not standard.exists() and time.monotonic() < end:
        time.sleep(0.1)
    assert (
        rpc(standard, {"operation": "desktop.delegation.status"})["data"]["enabled"]
        is False
    )
    expect(command(9 + extra_commands, "open"), "open", False)
    assert fixture()["count"] == before + expected_effects
    print(
        "PASS Stop persists across signed resident restart; old ownership is not restored",
        flush=True,
    )

    (root / "result.json").write_text(
        json.dumps(
            {
                "passed": True,
                "effects": expected_effects,
                "signedNativeOrigin": True,
                "signedOperatorApp": True,
                "provider": "native AX",
                "fixtureProvider": True,
            }
        )
    )
finally:
    cleanup_errors = []

    def restore_policy():
        if policy_changed:
            subprocess.run(
                ["/usr/bin/sudo", "-n", "/usr/bin/tee", str(policy) + ".qa-new"],
                input=policy_before,
                stdout=subprocess.DEVNULL,
                check=True,
            )
            subprocess.run(
                ["/usr/bin/sudo", "-n", "/bin/chmod", "644", str(policy) + ".qa-new"],
                check=True,
            )
            subprocess.run(
                [
                    "/usr/bin/sudo",
                    "-n",
                    "/bin/mv",
                    str(policy) + ".qa-new",
                    str(policy),
                ],
                check=True,
            )

    def stop_owned_processes():
        descendants = []
        if len(processes) > 1:
            rows = subprocess.run(
                ["/bin/ps", "-axo", "pid=,ppid=,command="],
                capture_output=True,
                text=True,
            ).stdout.splitlines()
            known = {processes[-1].pid}
            for _ in range(10):
                for row in rows:
                    columns = row.strip().split(None, 2)
                    if (
                        len(columns) == 3
                        and int(columns[1]) in known
                        and int(columns[0]) not in known
                    ):
                        known.add(int(columns[0]))
                        descendants.append((int(columns[0]), columns[2]))
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        for pid, identity in reversed(descendants):
            current = subprocess.run(
                ["/bin/ps", "-p", str(pid), "-o", "command="],
                capture_output=True,
                text=True,
            ).stdout.strip()
            if current == identity:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        # Exact fixture provider identity, never a broad process-name kill.
        runtime_path = root / "agent-runtime.json"
        if runtime_path.exists():
            pid = readjson(runtime_path)["pid"]
            check = subprocess.run(
                ["/bin/ps", "-p", str(pid), "-o", "command="],
                capture_output=True,
                text=True,
            )
            if str(root / "codex-fixture.py") in check.stdout:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        if fixture_started and fixture_pid is not None:
            check = subprocess.run(
                ["/bin/ps", "-p", str(fixture_pid), "-o", "command="],
                capture_output=True,
                text=True,
            )
            if str(home / "Applications/Machine Control Fixture.app") in check.stdout:
                try:
                    os.kill(fixture_pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def restore_application():
        if ya_installed:
            subprocess.run(["/bin/rm", "-rf", str(canonical)], check=True)
        if backup.exists():
            os.rename(backup, canonical)

    def restore_operator_state_and_socket():
        if shifted:
            for name, data in state_before.items():
                path = standard.parent / name
                if data is None:
                    if path.exists():
                        path.unlink()
                else:
                    temporary = path.with_name(path.name + ".qa-restore")
                    descriptor = os.open(
                        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                    )
                    with os.fdopen(descriptor, "wb") as file:
                        file.write(data)
                        file.flush()
                        os.fsync(file.fileno())
                    os.replace(temporary, path)
            if standard.exists():
                standard.unlink()
            os.rename(upstream, standard)

    for work in (
        stop_owned_processes,
        restore_policy,
        restore_application,
        restore_operator_state_and_socket,
    ):
        try:
            work()
        except BaseException as error:
            cleanup_errors.append(type(error).__name__)
    if cleanup_errors:
        raise RuntimeError(
            "Fixture cleanup incomplete; retain private recovery material"
        )
    assert policy.read_bytes() == policy_before, "Policy restoration differed"
    assert (
        standard.stat().st_ino == original_socket_inode
    ), "Original native socket was not restored"
    assert (
        canonical.stat().st_ino if canonical.exists() else None
    ) == original_ya_inode, "Previous YA application was not restored"
    for name, expected in state_before.items():
        path = standard.parent / name
        assert (
            path.read_bytes() if path.exists() else None
        ) == expected, "Operator state restoration differed"
    (root / "restoration.json").write_text(json.dumps({"passed": True}))
    print(
        "Existing testbed native socket restored; isolated YA and broker stopped",
        flush=True,
    )
