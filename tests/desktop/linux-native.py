#!/usr/bin/env python3
"""Native ordinary-user companion acceptance with independent GTK file effects."""

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--runtime", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--consent-actor", type=Path, required=True)
parser.add_argument("--fixture", type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.runtime))
import linuxui

results = []
owned = []
child = None
unit = "mc-desktop-native-fixture.service"
fixture_state = args.output.with_suffix(".fixture.json")
fixture_source = args.output.with_suffix(".fixture.py")


def check(name, value):
    results.append({"name": name, "passed": bool(value)})
    args.output.write_text(json.dumps({"complete": False, "passed": False,
                                     "checks": results}, indent=2))
    if not value:
        raise AssertionError(name)


def poll(fn, timeout=8):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = fn()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for independent effect")


def operator(method, **parameters):
    child.stdin.write(json.dumps({"method": method, **parameters}) + "\n")
    child.stdin.flush()
    if not select.select([child.stdout], [], [], 8)[0]:
        raise AssertionError("Private operator did not respond")
    return json.loads(child.stdout.readline())


def call(operation, **parameters):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(30)
        client.connect(str(endpoint))
        client.sendall(json.dumps({"operation": operation, **parameters}).encode() + b"\n")
        with client.makefile("rb") as reader:
            return json.loads(reader.readline(24 * 1024 * 1024))


def fixture():
    return json.loads(fixture_state.read_text())


def snapshot(query=None):
    result = call("snapshot", target="machine-control-fixture", query=query or "", maxDepth=16)
    check("fixture snapshot accepted", result["accepted"])
    return result["data"]["elements"]


def approval_button(label):
    app = poll(lambda: next((a for a in linuxui.application_roots(linuxui.desktop())
               if linuxui.safe(a.get_name, "") == "machine-control-approval"), None))
    nodes = [(n, i) for n, i in linuxui.walk(app, 16, 1000)
             if i["name"] == label and i["role"] == "push button"]
    check("unambiguous native approval button", len(nodes) == 1)
    check("native approval delivered", nodes[0][0].do_action(0))


try:
    log = args.output.with_suffix(".log").open("w")
    child = subprocess.Popen(["/usr/bin/python3", str(args.runtime / "desktop.py")],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)
    reply = operator("hello", processId=os.getpid(), executable="/usr/bin/true")
    check("private inherited handshake", reply["ok"])
    state = operator("state")["state"]
    endpoint = Path(state["socket"])
    check("off by default", state["deployment"]["grant"] is None)
    check("ordinary profile", call("capabilities")["data"]["privilege"] == "ordinary_user")
    check("off refuses observation", call("snapshot")["errorCode"] == "approval_required")
    check("public endpoint cannot approve", not call("decision", allow=True)["accepted"])
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as oversized:
        oversized.settimeout(5)
        oversized.connect(str(endpoint))
        oversized.sendall(b"{\"operation\":\"snapshot\",\"text\":\"" + b"x" * 65536 + b"\"}\n")
        try:
            refused = oversized.recv(1) == b""
        except ConnectionResetError:
            refused = True
        check("bounded invalid frame", refused)

    fixture_source.write_text(args.fixture.read_text().replace(
        'Path.home() / ".cache/linuxvm-testbed/fixture/state.json"', repr(str(fixture_state))))
    # Convert the substituted literal back into a Path; no shared oracle is changed.
    fixture_source.write_text(fixture_source.read_text().replace(
        "STATE_PATH = " + repr(str(fixture_state)), "STATE_PATH = Path(" + repr(str(fixture_state)) + ")"))
    fixture_state.unlink(missing_ok=True)
    subprocess.run(["systemd-run", "--user", "--quiet", "--collect", "--unit", unit,
                    "/usr/bin/python3", str(fixture_source)], check=True)
    poll(lambda: fixture_state.exists())
    check("manual grant", operator("arm", scopes=["observe", "control"], duration=60)["ok"])
    nodes = snapshot()
    button = next(n for n in nodes if n["label"] == "Semantic Increment" and n["role"] == "button")
    before = fixture()["semanticPresses"]
    check("semantic delivery", call("action", reference=button["reference"])["accepted"])
    poll(lambda: fixture()["semanticPresses"] == before + 1)
    check("independent semantic effect", fixture()["semanticPresses"] == before + 1)
    generation = call("status")["generation"]
    check("Stop", operator("stop")["ok"])
    check("old generation refused", call("snapshot", expectedGeneration=generation)["errorCode"] == "stale_generation")

    with concurrent.futures.ThreadPoolExecutor() as pool:
        denial = pool.submit(call, "grant.request", scopes=["observe", "control"],
                             reason="Native denial fixture", durationSeconds=30)
        poll(lambda: operator("state")["state"]["pending"])
        approval_button("Deny")
        check("native denial", denial.result()["errorCode"] == "approval_denied")
        approval = pool.submit(call, "grant.request", scopes=["observe", "control"],
                               reason="Native approval fixture", durationSeconds=30)
        poll(lambda: operator("state")["state"]["pending"])
        check("prompt pauses input", call("input.key", key="enter")["errorCode"] == "approval_prompt_visible")
        approval_button("Allow")
        check("native approval", approval.result()["accepted"])

    check("Stop before portal setup", operator("stop")["ok"])
    check("portal pending is asynchronous", operator("permission")["ok"])
    consent = subprocess.Popen(["/usr/bin/python3", str(args.consent_actor), "--runtime", str(args.runtime)],
                               stdout=log, stderr=log)
    owned.append(consent)
    poll(lambda: operator("state")["state"]["portal"]["state"] == "ready", 25)
    consent.wait(5)
    check("visible portal consent", consent.returncode == 0)
    check("portal input capabilities", operator("state")["state"]["portal"]["keyboard"])
    check("grant after portal", operator("arm", scopes=["observe", "control"], duration=30)["ok"])
    activation = call("application.activate", target="machine-control-fixture")
    print("ACTIVATION", json.dumps(activation),file=log,flush=True)
    check("unsupported top-level activation is explicit", activation.get("errorCode") == "activation_unsupported")
    subprocess.run(["systemctl", "--user", "stop", unit], check=True)
    fixture_state.unlink()
    subprocess.run(["systemd-run", "--user", "--quiet", "--collect", "--unit", unit,
                    "/usr/bin/python3", str(fixture_source)], check=True)
    poll(lambda: fixture_state.exists())
    time.sleep(0.3)
    image = call("capture")
    check("portal capture", image["accepted"] and image["actualRoute"] == "user/linux.portal-pipewire")
    artifact = image["data"]["artifact"]
    png = Path(artifact["guestPath"]).read_bytes()
    check("capture hash", hashlib.sha256(png).hexdigest() == artifact["sha256"])
    check("capture dimensions", artifact["width"] > 0 and artifact["height"] > 0)
    nodes = snapshot()
    canvas = next(n for n in nodes if n["label"] == "Visual Canvas")
    bounds = canvas["bounds"]
    before = fixture()["visualClicks"]
    click = call("input.click", x=bounds["x"] + bounds["width"] / 2,
                 y=bounds["y"] + bounds["height"] / 2)
    check("portal pointer delivery", click["accepted"] and click["actualRoute"] == "user/linux.portal-notify")
    poll(lambda: fixture()["visualClicks"] == before + 1)
    check("independent pointer effect", fixture()["visualClicks"] == before + 1)
    center = {"x": bounds["x"] + bounds["width"] / 2, "y": bounds["y"] + bounds["height"] / 2}
    before = fixture()["visualClicks"]
    check("double-click delivery", call("input.click", **center, count=2)["accepted"])
    poll(lambda: fixture()["visualClicks"] >= before + 2)
    check("independent double-click effect", True)
    releases = fixture()["dragReleases"]
    check("drag delivery", call("input.drag", x1=center["x"] - 40, y1=center["y"],
                                x2=center["x"] + 40, y2=center["y"] + 20)["accepted"])
    poll(lambda: fixture()["dragReleases"] > releases)
    check("independent drag effect", True)
    previous_scroll = fixture()["scrollY"]
    check("scroll delivery", call("input.scroll", **center, dy=-2)["accepted"])
    poll(lambda: fixture()["scrollY"] != previous_scroll)
    check("independent scroll effect", True)
    entry = next(n for n in nodes if n["label"] == "Fixture Text")
    check("semantic focus", call("focus", reference=entry["reference"])["accepted"])
    check("clear entry", call("input.key", key="ctrl+a")["accepted"])
    check("Unicode delivery", call("input.text", text="Linux 世界 café")["accepted"])
    poll(lambda: fixture()["text"] == "Linux 世界 café")
    check("independent Unicode effect", fixture()["text"] == "Linux 世界 café")
    old = entry["reference"]
    check("sharing disconnect", operator("permission.disconnect")["ok"])
    check("sharing closes grant", operator("state")["state"]["deployment"]["grant"] is None)
    check("re-arm semantic grant", operator("arm", scopes=["observe", "control"], duration=2)["ok"])
    check("stale reference refused", call("focus", reference=old)["errorCode"] == "stale_reference")
    time.sleep(2.1)
    check("expiry", call("snapshot")["errorCode"] == "approval_required")
    check("update gate", operator("prepare_update")["ok"])
    check("update refuses grant", not operator("arm", scopes=["observe"], duration=2)["ok"])
    check("cancel update", operator("cancel_update")["ok"])
    check("Quit", operator("quit")["ok"])
    child.wait(5)
    check("owned endpoint removed", not endpoint.exists())
    args.output.write_text(json.dumps({"complete": True, "passed": all(v["passed"] for v in results),
                                     "checks": results}, indent=2))
except BaseException as error:
    args.output.write_text(json.dumps({"complete": True, "passed": False,
                                     "failure": str(error), "checks": results}, indent=2))
    raise
finally:
    if child and child.poll() is None:
        child.stdin.close()
        try:
            child.wait(5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
    for process in owned:
        if process.poll() is None:
            process.terminate()
        process.wait()
    subprocess.run(["systemctl", "--user", "stop", unit], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fixture_source.unlink(missing_ok=True)
    fixture_state.unlink(missing_ok=True)
