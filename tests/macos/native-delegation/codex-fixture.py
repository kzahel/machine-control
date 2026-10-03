#!/usr/bin/env python3
# Owned app-server protocol fixture: no model, sub-agent or real provider credentials.
import sys, os, json, pathlib, threading, time, subprocess, select, atexit

root = pathlib.Path(__file__).resolve().parent
if "--version" in sys.argv:
    print("codex-cli 0.128.0")
    sys.exit(0)
if sys.argv[1:] == ["login", "status"]:
    print("Logged in using ChatGPT")
    sys.exit(0)
if os.getenv("MACHINE_CONTROL_DESKTOP_PROXY"):
    (root / "agent-runtime.json").write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "delegated": bool(os.getenv("MACHINE_CONTROL_DESKTOP_PROXY")),
                "proxy": os.getenv("MACHINE_CONTROL_DESKTOP_PROXY"),
            }
        )
    )
children = []


@atexit.register
def cleanup():
    for child in children:
        if child.poll() is None:
            child.terminate()


def worker():
    child = None
    active = {}
    seq = 0

    def rpc(operation, **fields):
        nonlocal seq
        seq += 1
        request = {"operation": operation, "requestId": str(seq), **fields}
        child.stdin.write(json.dumps(request) + "\n")
        child.stdin.flush()
        if not select.select([child.stdout], [], [], 12)[0]:
            raise RuntimeError("fixture control response timeout")
        line = child.stdout.readline()
        if not line:
            raise RuntimeError("fixture transport ended")
        response = json.loads(line)
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        with open(root / "protocol.private.log", "a") as record:
            record.write(
                json.dumps(
                    {
                        "operation": operation,
                        "accepted": response.get("accepted"),
                        "errorCode": response.get("errorCode"),
                        "state": data.get("state"),
                        "terminalReason": data.get("terminalReason"),
                        "time": time.monotonic(),
                        "blockingReasons": data.get("blockingReasons"),
                        "providerAccepted": data.get("accepted"),
                        "providerError": data.get("errorCode"),
                        "providerMessage": data.get("message"),
                    }
                )
                + "\n"
            )
        return response

    for index in range(1, 20):
        trigger = root / f"command-{index}.json"
        until = time.monotonic() + 180
        heartbeat = time.monotonic()
        while not trigger.exists() and time.monotonic() < until:
            if child and active and time.monotonic() - heartbeat >= 1:
                try:
                    rpc("control.heartbeat")
                except:
                    pass
                heartbeat = time.monotonic()
            time.sleep(0.05)
        if not trigger.exists():
            return
        command = json.loads(trigger.read_text())
        result = {}
        try:
            if command["operation"] == "open":
                cli = root / "Machine Control.app/Contents/Resources/mc-cli"
                err = open(root / f"proxy-{index}.log", "w")
                child = subprocess.Popen(
                    [
                        str(cli / "python/bin/python3"),
                        "-I",
                        "-B",
                        str(cli / "platforms/macos/host/machost.py"),
                        "channel",
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=err,
                    text=True,
                    bufsize=1,
                )
                children.append(child)
                reply = rpc(
                    "control.open",
                    schema="machine-control-admission/v1",
                    reason="Signed native launch fixture",
                    scopes=["observe", "control"],
                    durationSeconds=120,
                    waitSeconds=120,
                )
                result = {
                    "open": reply.get("accepted"),
                    "errorCode": reply.get("errorCode"),
                }
                if reply.get("accepted"):
                    view = reply["data"]
                    end = time.monotonic() + 20
                    while view["state"] != "offered" and time.monotonic() < end:
                        time.sleep(0.2)
                        view = rpc("control.heartbeat")["data"]
                    active = rpc(
                        "control.accept", offerGeneration=view["offerGeneration"]
                    )["data"]
                    result.update(
                        state=active["state"], assurance=active.get("ownerAssurance")
                    )
            elif command["operation"] == "effect":
                rpc("control.heartbeat")
                snapshot = rpc(
                    "control.dispatch",
                    sessionId=active["sessionId"],
                    resourceGenerations=active["resourceGenerations"],
                    request={
                        "operation": "snapshot",
                        "provider": "macos-native",
                        "target": "org.machine-control.fixture",
                        "depth": 6,
                    },
                )
                nested = snapshot.get("data") or {}
                if nested.get("accepted"):
                    button = next(
                        e
                        for e in nested["data"]["elements"]
                        if e.get("identifier") == "fixture.increment"
                        or e.get("title") == "Increment"
                    )
                    rpc("control.heartbeat")
                    action = rpc(
                        "control.dispatch",
                        sessionId=active["sessionId"],
                        resourceGenerations=active["resourceGenerations"],
                        request={
                            "operation": "action",
                            "provider": "macos-native",
                            "action": "press",
                            "reference": button["reference"],
                        },
                    )
                    result = {
                        "accepted": action.get("data", {}).get("accepted"),
                        "errorCode": action.get("errorCode"),
                    }
                    rpc("control.heartbeat")
                    heartbeat = time.monotonic()
                else:
                    result = {
                        "accepted": False,
                        "errorCode": snapshot.get("errorCode")
                        or nested.get("errorCode"),
                    }
            elif command["operation"] == "status":
                reply = rpc("control.heartbeat")
                result = {
                    "accepted": reply.get("accepted"),
                    "state": reply.get("data", {}).get("state"),
                    "errorCode": reply.get("errorCode"),
                }
            elif command["operation"] == "accept":
                view = rpc("control.heartbeat")["data"]
                end = time.monotonic() + 30
                while (
                    view["state"] not in ["offered", "ended"] and time.monotonic() < end
                ):
                    time.sleep(0.2)
                    view = rpc("control.heartbeat")["data"]
                active = (
                    rpc("control.accept", offerGeneration=view["offerGeneration"]).get(
                        "data"
                    )
                    or {}
                )
                result = {"state": active.get("state")}
            elif command["operation"] == "close":
                result = {"accepted": rpc("control.cancel").get("accepted")}
                child.stdin.close()
                child.wait(timeout=5)
                child = None
        except Exception as e:
            result = {"fixtureError": str(e)}
        (root / f"result-{index}.json").write_text(json.dumps(result))


if os.getenv("MACHINE_CONTROL_DESKTOP_PROXY"):
    threading.Thread(target=worker, daemon=True).start()


def write(value):
    print(json.dumps(value), flush=True)


for line in sys.stdin:
    try:
        message = json.loads(line)
    except:
        continue
    if "id" not in message:
        continue
    method = message.get("method")
    params = message.get("params", {})
    if method == "initialize":
        result = {"userAgent": "codex-conformance-fixture"}
    elif method in ["thread/start", "thread/resume"]:
        result = {
            "thread": {"id": params.get("threadId", "native-delegation-fixture")},
            "model": "gpt-6",
            "reasoningEffort": "low",
        }
    elif method == "turn/start":
        result = {"turn": {"id": "fixture-turn", "status": "inProgress", "error": None}}
    elif method == "model/list":
        result = {
            "data": [
                {
                    "id": "gpt-6",
                    "model": "gpt-6",
                    "displayName": "Conformance fixture",
                    "isDefault": True,
                    "supportedReasoningEfforts": [
                        {"reasoningEffort": "low", "description": "Fixture"}
                    ],
                    "defaultReasoningEffort": "low",
                }
            ]
        }
    else:
        result = {}
    write({"id": message["id"], "result": result})
