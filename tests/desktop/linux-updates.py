#!/usr/bin/env python3
"""Signed AppImage replacement with live unified access through a localhost feed.

Guest-side acceptance of the operator-initiated update contract for unified
Desktop/Browser surface modes (0.7 and later). It drives only actual Settings
controls through AT-SPI, the tray through its StatusNotifier menu, and agent
tasks through ordinary v2 `control.open` owners. It never sends operator
commands itself and never answers a native approval.

Covered behavior:

- live Desktop/Browser access leaves Install and restart enabled with the
  pause/restore note;
- a tampered download is refused without stopping or changing access;
- a failed replacement after Stop restores the same access immediately;
- a running or waiting agent task requires Install anyway, and Cancel leaves
  everything unchanged;
- a verified download is complete before access stops; the one-shot plan is
  written before replacement and consumed by the updated client, which replays
  the same modes and exact profiles while timed consent keeps its original
  wall-clock end;
- exact signed incoming bytes, new runtime generation, exact source, refusal of
  pre-update session fences and a surviving, reconnecting test browser; and
- access that was Off before replacement stays Off afterwards.

The claimed controller owns the disposable target, staging, a loopback-only
resolution of the production update host, unprivileged binding of port 443,
the disposable test CA (`--ca`, passed to the app as SSL_CERT_FILE), the
separately identified test browser and its sandbox helper, cleanup and power.
The app runs with isolated XDG config/data/state/cache roots below `--output`,
including a recording URI handler so `browser.setup` never opens a real
browser. Raw evidence stays private; it contains no credentials.
"""

import argparse
import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

FEED_HOST = "machinecontrol.dev"
FEED_PREFIX = "/updates/tauri/linux/"
DOWNLOAD_PATH = "/mc-update-acceptance/MachineControl.AppImage"
PLAN_NAME = "update-access-resume.json"
APP_DATA = "org.machine-control.app"
EXTENSION_ID = "ncbfifkjllmnkkjmomjohinigfgdocjc"
PAUSE_NOTE = "Access pauses while Machine Control restarts, then turns back on."
RESTORED_NOTE = "Access was turned back on after the update."
CONFIRM_NOTE = "An agent task is running or waiting."
# Native consent is rounded to whole seconds when recorded and replayed.
END_TOLERANCE = 5

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
for name in ["app", "sender", "incoming", "tls-cert", "tls-key", "ca", "runtime", "source-root", "output"]:
    parser.add_argument("--" + name, type=Path, required=True)
parser.add_argument("--revision", required=True, help="Exact source revision of both candidates")
parser.add_argument("--sender-version", required=True)
parser.add_argument("--incoming-version", required=True)
parser.add_argument("--chrome", type=Path, help="Separately identified test browser; omit for Desktop-only")
parser.add_argument("--chrome-no-sandbox", action="store_true",
                    help="Explicit disposable-VM fixture only; prefer a supplied CHROME_DEVEL_SANDBOX helper")
args = parser.parse_args()
args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(143)))
sys.dont_write_bytecode = True
sys.path.insert(0, str(args.runtime))
import linuxui  # noqa: E402
from gi.repository import Gio, GLib  # noqa: E402

linuxui.Atspi.init()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


actor = load("surface_owner", args.source_root / "tests/macos/surface-policy-live.py")
cdp = load("fixture_cdp", args.source_root / "platforms/chromeos/cdp.py") if args.chrome else None

app_path = args.app.resolve()
folder_mode = app_path.parent.stat().st_mode & 0o777
endpoint = Path(os.environ["XDG_RUNTIME_DIR"]) / "machine-control-desktop/desktop.sock"
xdg = {name: args.output / suffix for name, suffix in [
    ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
    ("XDG_STATE_HOME", "state"), ("XDG_CACHE_HOME", "cache")]}
plan_path = xdg["XDG_DATA_HOME"] / APP_DATA / PLAN_NAME
store_log = args.output / "store-uris.txt"
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
log = (args.output / "updates.log").open("w")
checks = []
observations = {"skipped": []}
failure = None
process = chrome = web = None
feeds = []
owners = []
effects = {"clicks": 0, "text": ""}
stop_threads = threading.Event()


def report(complete=False):
    value = dict(complete=complete, passed=complete and failure is None and bool(checks),
                 failure=failure, checks=checks, observations=observations)
    temporary = args.output / "summary.tmp.json"
    temporary.write_text(json.dumps(value, indent=2, default=str))
    temporary.replace(args.output / "summary.json")


def check(name, value, **detail):
    checks.append(dict(name=name, passed=bool(value), **({"detail": detail} if detail else {})))
    report()
    if not value:
        raise AssertionError(name + (" " + json.dumps(detail, default=str) if detail else ""))


def note(key, value):
    observations[key] = value
    report()


def pump():
    context = GLib.MainContext.default()
    for _ in range(64):
        if not context.pending():
            break
        context.iteration(False)


def poll(fn, label, timeout=30, interval=.5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pump()
        try:
            value = fn()
            if value:
                return value
        except (OSError, ValueError, KeyError, linuxui.UIError, GLib.Error):
            pass
        time.sleep(interval)
    raise AssertionError("Timed out: " + label)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def plain(operation, **fields):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
        peer.settimeout(20)
        peer.connect(str(endpoint))
        peer.sendall(json.dumps(dict(operation=operation, **fields)).encode() + b"\n")
        with peer.makefile("rb") as stream:
            return json.loads(stream.readline(16 * 1024 * 1024))


def status():
    value = plain("status")
    if not value.get("accepted"):
        raise ValueError(value.get("errorCode"))
    return value


def surfaces():
    """Comparable live consent: mode, exact profiles and wall-clock end."""
    now = time.time()
    rows = status()["data"]["admission"]["surfaces"]
    result = {}
    for name, row in rows.items():
        remaining = row.get("consentRemainingSeconds")
        live = row.get("mode") != "off" and not row.get("expired")
        result[name] = dict(mode=row.get("mode"), expired=row.get("expired"),
                            profileIds=sorted(row.get("profileIds") or []),
                            remainingSeconds=remaining,
                            end=(now + remaining) if live and remaining is not None else None)
    return result


def same_access(before, after):
    for name in ("desktop", "browser"):
        a, b = before[name], after[name]
        if (a["mode"], a["profileIds"], a["end"] is None) != (b["mode"], b["profileIds"], b["end"] is None):
            return False
        if a["end"] is not None and abs(a["end"] - b["end"]) > END_TOLERANCE:
            return False
    return True


def all_off(value):
    return all(row["mode"] == "off" for row in value.values())


def identity(path):
    return json.loads(subprocess.check_output([str(path), "--identity"], text=True, timeout=60))


def app_pids():
    """Processes of this exact AppImage, before and after self-replacement."""
    wanted = b"APPIMAGE=" + os.fsencode(str(app_path))
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        with contextlib.suppress(OSError):
            if wanted in (entry / "environ").read_bytes().split(b"\0"):
                found.append(int(entry.name))
    return found


def owned_root():
    pids = set(app_pids())
    roots = [root for root in linuxui.application_roots(linuxui.desktop())
             if linuxui.safe(root.get_name, "") == "machine-control"
             and linuxui.safe(root.get_process_id, 0) in pids]
    if len(roots) != 1:
        return None
    roots[0].clear_cache()
    return roots[0]


def nodes():
    root = owned_root()
    return list(linuxui.walk(root, 40, 4000)) if root else []


def find(label, roles=("push button",)):
    found = [node for node, info in nodes() if info["name"] == label and info["role"] in roles]
    return found[0] if len(found) == 1 else None


def text():
    values = []
    for node, info in nodes():
        values.append(info["name"])
        if "Text" in info["interfaces"]:
            values.append(linuxui.safe(lambda: linuxui.Atspi.Text.get_text(node, 0, -1), "") or "")
    return " ".join(values)


def press(label, roles=("push button",), timeout=30):
    node = poll(lambda: (n if (n := find(label, roles)) and "enabled" in linuxui.state_names(n) else None),
                "enabled native UI " + label, timeout)
    check("native UI " + label, node.do_action(0))
    time.sleep(.3)


def enabled(label):
    node = find(label)
    return node is not None and "enabled" in linuxui.state_names(node)


def switch(label, on):
    node = poll(lambda: find(label, ("toggle button",)), "switch " + label)
    if ("checked" in linuxui.state_names(node)) != on:
        check("native switch " + label, node.do_action(0))


def checkbox(label, on):
    node = poll(lambda: find(label, ("check box",)), "check box " + label)
    if ("checked" in linuxui.state_names(node)) != on:
        node.do_action(0)
    poll(lambda: ("checked" in linuxui.state_names(find(label, ("check box",)))) == on, "checked " + label)
    check("native check box " + label, True)


def expand(label):
    node = poll(lambda: find(label, ("unknown", "push button", "toggle button")), "disclosure " + label)
    if "expanded" not in linuxui.state_names(node):
        node.do_action(0)
    poll(lambda: "expanded" in linuxui.state_names(find(label, ("unknown", "push button", "toggle button"))),
         "expanded " + label)


def popup_cell(option):
    root = owned_root()
    for _, window in linuxui.children(root) if root else []:
        if linuxui.safe(window.get_role_name, "") == "frame":
            continue
        for node, info in linuxui.walk(window, 10, 200):
            if info["role"] == "table cell" and info["name"] == option and "showing" in info["states"]:
                return node
    return None


def choose(label, option):
    """Select a native WebKit option through accessibility actions only."""
    combo = poll(lambda: find(label, ("combo box",)), "combo " + label)
    combo.clear_cache()
    menu = next((child for _, child in linuxui.children(combo)), None)
    items = [child for _, child in linuxui.children(menu)] if menu is not None else []
    item = next((child for child in items if linuxui.safe(child.get_name, "") == option), None)
    if item is not None:
        check("native option " + option, item.do_action(0))
        def selected():
            current = find(label, ("combo box",))
            current.clear_cache()
            listing = next(child for _, child in linuxui.children(current))
            return any(linuxui.safe(c.get_name, "") == option and "selected" in linuxui.state_names(c)
                       for _, c in linuxui.children(listing))
        poll(selected, "selected " + option)
        return
    # WebKit exposes collapsed-details options only through the opened list.
    with contextlib.suppress(Exception):
        combo.scroll_to(linuxui.Atspi.ScrollType.ANYWHERE)
    combo.do_action(0)
    cell = poll(lambda: popup_cell(option), "native option list " + option)
    index = next(a["index"] for a in linuxui.actions(cell) if a["name"] == "Activate")
    check("native option " + option, cell.do_action(index))
    poll(lambda: popup_cell(option) is None, "closed option list")


def dbus(destination, path, interface, method, parameters):
    return bus.call_sync(destination, path, interface, method, parameters, None,
                         Gio.DBusCallFlags.NONE, 3000, None).unpack()


def menu(label):
    """Activate the actual tray item by its visible label."""
    items = dbus("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher", "org.freedesktop.DBus.Properties", "Get",
                 GLib.Variant("(ss)", ("org.kde.StatusNotifierWatcher", "RegisteredStatusNotifierItems")))[0]
    for item in items:
        if "@" not in item or "tray_app_control" not in item:
            continue
        destination, path = item.split("@", 1)
        properties = dbus(destination, path, "org.freedesktop.DBus.Properties", "GetAll",
                          GLib.Variant("(s)", ("org.kde.StatusNotifierItem",)))[0]
        layout = dbus(destination, properties["Menu"], "com.canonical.dbusmenu", "GetLayout",
                      GLib.Variant("(iias)", (0, -1, [])))[1]
        pending = [layout]
        while pending:
            identifier, fields, children = pending.pop()
            if fields.get("label", "").replace("_", "") == label:
                dbus(destination, properties["Menu"], "com.canonical.dbusmenu", "Event",
                     GLib.Variant("(isvu)", (identifier, "clicked", GLib.Variant("i", 0), 0)))
                time.sleep(.3)
                return True
            pending.extend(children)
    raise AssertionError("Missing tray item " + label)


class PlanWatcher(threading.Thread):
    """Record every observed version of the one-shot plan file."""

    def __init__(self):
        super().__init__(daemon=True)
        self.events = []
        self.previous = None

    def run(self):
        while not stop_threads.wait(.02):
            try:
                content = plan_path.read_bytes()
            except FileNotFoundError:
                content = None
            except OSError:
                continue
            if content != self.previous:
                event = dict(at=time.time(), present=content is not None)
                if content is not None:
                    with contextlib.suppress(ValueError):
                        event["plan"] = json.loads(content)
                    event["mode"] = oct(plan_path.stat().st_mode & 0o777) if plan_path.exists() else None
                self.events.append(event)
                self.previous = content

    def plans(self, since=0):
        return [e for e in self.events if e["at"] >= since and e["present"]]


class PolicyWatcher(threading.Thread):
    """Record runtime generation and surface-mode transitions."""

    def __init__(self):
        super().__init__(daemon=True)
        self.events = []
        self.previous = None

    def run(self):
        while not stop_threads.wait(.25):
            try:
                value = plain("status")
                rows = value["data"]["admission"]["surfaces"]
                current = (value.get("generation"), rows["desktop"]["mode"], rows["browser"]["mode"],
                           value["data"]["admission"].get("active"), value["data"]["admission"].get("waiting"))
            except (OSError, ValueError, KeyError, TypeError):
                current = None
            if current != self.previous:
                self.events.append(dict(at=time.time(), state=current))
                self.previous = current

    def saw_off_between(self, start, end):
        return any(start <= e["at"] <= end and e["state"] and e["state"][1] == "off" and e["state"][2] == "off"
                   for e in self.events)


plans = PlanWatcher()
policies = PolicyWatcher()


class Feed(BaseHTTPRequestHandler):
    mode = "normal"
    started = threading.Event()
    release = threading.Event()
    requests = []

    def log_message(self, *_):
        pass

    def do_GET(self):
        Feed.requests.append(dict(at=time.time(), path=self.path, mode=Feed.mode))
        print("HTTPS fixture request:", self.path, Feed.mode, file=log, flush=True)
        if self.path.startswith(FEED_PREFIX):
            parts = self.path[len(FEED_PREFIX):].split("?", 1)[0].split("/")
            if len(parts) != 2:
                self.send_error(404)
                return
            arch, current = parts
            if current == args.incoming_version:
                self.send_response(204)
                self.end_headers()
                return
            body = json.dumps({"version": args.incoming_version, "notes": "Linux update acceptance",
                               "pub_date": "2026-11-06T00:00:00Z", "platforms": {
                                   "linux-" + arch: {"url": "https://" + FEED_HOST + DOWNLOAD_PATH,
                                                     "signature": Path(str(args.incoming) + ".sig").read_text().strip()}}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == DOWNLOAD_PATH:
            mode = Feed.mode
            record = Feed.requests[-1] if Feed.requests[-1]["path"] == self.path else {}
            size = args.incoming.stat().st_size
            self.send_response(200)
            self.send_header("Content-Length", str(size + (8 if mode == "tampered" else 0)))
            self.end_headers()
            with args.incoming.open("rb") as source:
                self.wfile.write(source.read(65536))
                self.wfile.flush()
                Feed.started.set()
                if mode == "pause" and not Feed.release.wait(60):
                    return
                shutil.copyfileobj(source, self.wfile)
                if mode == "tampered":
                    self.wfile.write(b"tampered")
            record["completedAt"] = time.time()
        else:
            self.send_error(404)


class BrowserFixture(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path.startswith("/effect?"):
            values = parse_qs(urlsplit(self.path).query)
            if "click" in values:
                effects["clicks"] += 1
            if "text" in values:
                effects["text"] = values["text"][0]
            body = b"ok"
        else:
            body = b'''<!doctype html><title>Linux update browser fixture</title>
<button onclick="fetch('/effect?click=1')">Increment</button>
<input aria-label="Fixture text" oninput="fetch('/effect?text='+encodeURIComponent(this.value))">'''
        self.send_response(200)
        self.send_header("Content-Type", "text/html;charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve_feed():
    addresses = sorted({info[4][0] for info in socket.getaddrinfo(FEED_HOST, 443, proto=socket.IPPROTO_TCP)})
    check("production update host resolves only to loopback",
          addresses and all(ipaddress.ip_address(a.split("%")[0]).is_loopback for a in addresses), addresses=addresses)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(args.tls_cert, args.tls_key)
    for address in addresses:
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        server_class = type("FeedServer", (ThreadingHTTPServer,), {"address_family": family})
        server = server_class((address, 443), Feed)
        server.socket = tls.wrap_socket(server.socket, server_side=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        feeds.append(server)


def isolated_environment():
    env = {key: value for key, value in os.environ.items()
           if key not in ("APPIMAGE", "APPDIR", "ARGV0", "OWD", "SSL_CERT_DIR")}
    for name, path in xdg.items():
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        env[name] = str(path)
    env["SSL_CERT_FILE"] = str(args.ca)
    # browser.setup opens the Chrome Web Store; record that URI instead of
    # launching a real browser from the isolated configuration.
    handler = args.output / "record-uri"
    handler.write_text("#!/bin/sh\nprintf '%s\\n' \"$1\" >> " + json.dumps(str(store_log)) + "\n")
    handler.chmod(0o700)
    applications = xdg["XDG_DATA_HOME"] / "applications"
    applications.mkdir(exist_ok=True)
    (applications / "mc-update-store-fixture.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Store link fixture\nNoDisplay=true\n"
        "Exec=" + str(handler) + " %u\nMimeType=x-scheme-handler/https;x-scheme-handler/http;\n")
    (xdg["XDG_CONFIG_HOME"] / "mimeapps.list").write_text(
        "[Default Applications]\nx-scheme-handler/https=mc-update-store-fixture.desktop\n"
        "x-scheme-handler/http=mc-update-store-fixture.desktop\n")
    return env


def launch(env):
    global process
    process = subprocess.Popen([str(app_path), "--settings"], env=env, stdout=log, stderr=log,
                               start_new_session=True)
    poll(lambda: status()["data"].get("ready"), "packaged companion", 60)
    poll(lambda: find("Settings"), "Settings window", 45)
    return status()


def quit_app():
    menu("Quit Machine Control")
    poll(lambda: not endpoint.exists() and not app_pids(), "Quit removes endpoint and processes", 30)


def page(name):
    press(name)


def check_for_update():
    page("Settings")
    press("Check for updates")
    poll(lambda: enabled("Install and restart"), "enabled Install and restart", 60)


def diagnostics(since):
    """Supervisor update diagnostics (codes only) recorded after `since`."""
    rows = []
    for path in sorted((xdg["XDG_STATE_HOME"] / "machine-control/logs/diagnostics").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            with contextlib.suppress(ValueError):
                value = json.loads(line)
                if value.get("atUnixMs", 0) / 1000 >= since and value.get("operation", "").startswith("update."):
                    rows.append(dict(at=value["atUnixMs"] / 1000, operation=value["operation"], version=value.get("version")))
    return rows


def codes(since):
    return [row["operation"] for row in diagnostics(since)]


def relaunched(generation, label, since):
    """The replacement runtime, or a failure naming supervisor startup codes."""
    try:
        return poll(lambda: (value if (value := status())["generation"] != generation
                             and value["data"].get("ready") else None), label, 90)
    except AssertionError:
        raise AssertionError(label + " failed; supervisor codes " + json.dumps(diagnostics(since))) from None


def plan_absent():
    return not plan_path.exists()


def owner(surfaces_, profiles=(), wait=True):
    value = actor.Owner(endpoint, "linux-update-acceptance", surfaces_, profiles=list(profiles), duration=300)
    owners.append(value)
    if wait:
        value.wait()
    return value


def close_owner(value):
    with contextlib.suppress(Exception):
        value.close()
    with contextlib.suppress(ValueError):
        owners.remove(value)


def browser(task, operation, **fields):
    """One owner-bound Browser operation; returns its accepted provider data."""
    result = task.call(operation, **fields)
    if not result.get("accepted"):
        raise ValueError(operation + " refused: " + str(result.get("errorCode")))
    return result.get("data", {})


def stale_reference(task, profile, reference):
    """A pre-update element reference must not retarget in a new runtime."""
    clicks = effects["clicks"]
    try:
        result = task.call("browser.click", browserProfileId=profile, reference=reference)
        refusal = None if result.get("accepted") else result.get("errorCode")
    except AssertionError as error:
        refusal = str(error)
    time.sleep(1.5)
    return refusal, effects["clicks"] - clicks


def browser_effects(profile, url, label, stale=None):
    task = owner(["browser"], [profile])
    check(label + " Browser task active", task.view["state"] == "active")
    if stale:
        refusal, clicked = stale_reference(task, profile, stale)
        note("staleReference", dict(errorCode=refusal, clickEffects=clicked))
        check("pre-update element reference refused without effect", refusal is not None and clicked == 0,
              errorCode=refusal, clickEffects=clicked)
    tabs = browser(task, "browser.tabs", browserProfileId=profile)["tabs"]
    tab = tabs[0]["tabId"]
    browser(task, "browser.navigate", browserProfileId=profile, tabId=tab, url=url)
    poll(lambda: any(t.get("url") == url for t in browser(task, "browser.tabs", browserProfileId=profile)["tabs"]),
         label + " navigation")
    snapshot = poll(lambda: browser(task, "browser.snapshot", browserProfileId=profile, tabId=tab).get("elements"),
                    label + " snapshot")
    button = next(n for n in snapshot if n["name"] == "Increment" and n["role"] == "button")
    entry = next(n for n in snapshot if n["name"] == "Fixture text" and n["role"] == "textbox")
    clicks = effects["clicks"]
    browser(task, "browser.click", browserProfileId=profile, reference=button["reference"])
    poll(lambda: effects["clicks"] == clicks + 1, label + " click effect")
    check(label + " independent Browser click effect", True)
    words = label + " Linux 世界 café"
    browser(task, "browser.type", browserProfileId=profile, reference=entry["reference"], text=words)
    poll(lambda: effects["text"] == words, label + " Unicode effect")
    check(label + " independent Browser Unicode effect", True)
    fence = dict(sessionId=task.view["sessionId"], resourceGenerations=task.view["resourceGenerations"])
    return task, fence, button["reference"]


def setup_browser():
    global chrome, web
    page("Permissions")
    press("Install Chrome extension from the Web Store")
    extension = xdg["XDG_DATA_HOME"] / "machine-control/extension"
    poll(lambda: (extension / "manifest.json").exists() and store_log.exists(), "bundled extension and store link")
    check("Settings registers host and opens only the recorded store link",
          store_log.read_text().strip().startswith("https://chromewebstore.google.com/"))
    profile = args.output / "chrome-profile"
    hosts = profile / "NativeMessagingHosts"
    hosts.mkdir(parents=True)
    manifest = "org.machine_control.browser.json"
    shutil.copyfile(xdg["XDG_CONFIG_HOME"] / "google-chrome-for-testing/NativeMessagingHosts" / manifest, hosts / manifest)
    (hosts / manifest).chmod(0o600)
    web = ThreadingHTTPServer(("127.0.0.1", 0), BrowserFixture)
    threading.Thread(target=web.serve_forever, daemon=True).start()
    chrome = subprocess.Popen([str(args.chrome), "--user-data-dir=" + str(profile), "--remote-debugging-port=0",
                               "--no-first-run", "--no-default-browser-check", "--no-proxy-server",
                               "--password-store=basic", "--disable-gpu", "--ozone-platform=wayland",
                               *(["--no-sandbox"] if args.chrome_no_sandbox else []),
                               "--disable-extensions-except=" + str(extension), "--load-extension=" + str(extension),
                               "about:blank"], stdout=log, stderr=log, start_new_session=True)
    port_file = profile / "DevToolsActivePort"
    poll(port_file.exists, "test browser DevTools port", 60)
    port, path = port_file.read_text().splitlines()[:2]
    connection = cdp.CDP("ws://127.0.0.1:" + port + path)
    try:
        for page_url in ["chrome://extensions/", "chrome-extension://" + EXTENSION_ID + "/panel.html"]:
            target = connection.call("Target.createTarget", url=page_url)["targetId"]
            def info():
                with urlopen("http://127.0.0.1:" + port + "/json/list", timeout=5) as response:
                    return next((row for row in json.load(response) if row["id"] == target), None)
            panel = cdp.CDP(poll(info, "extension page")["webSocketDebuggerUrl"])
            try:
                ready = ("typeof chrome!=='undefined' && !!chrome.developerPrivate" if page_url.startswith("chrome://")
                         else "!!document.getElementById('profile-name') && !document.getElementById('profile-card').hidden")
                poll(lambda: panel.call("Runtime.evaluate", expression=ready).get("result", {}).get("value"),
                     "loaded extension page", 45)
                expression = ("new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))"
                              if page_url.startswith("chrome://") else
                              "document.getElementById('profile-name').value='Work';"
                              "document.getElementById('profile-name').dispatchEvent(new Event('change'));"
                              "document.getElementById('profile-enabled').checked=true;"
                              "document.getElementById('profile-enabled').dispatchEvent(new Event('change'));true")
                response = panel.call("Runtime.evaluate", expression=expression, awaitPromise=True)
                assert "exceptionDetails" not in response, "Extension preference setup failed"
            finally:
                panel.close()
                connection.call("Target.closeTarget", targetId=target)
    finally:
        connection.close()
    def connected():
        rows = status()["data"]["browser"]["profiles"]
        return next((row for row in rows if row.get("name") == "Work" and row.get("enabled") and row.get("connected")), None)
    profile_row = poll(connected, "enabled connected test profile", 60)
    check("test browser profile connects through the registered host", True)
    return profile_row["profileId"], "http://127.0.0.1:" + str(web.server_port) + "/"


def enable_access(profile):
    page("Access")
    expand("More options")
    if profile:
        choose("Access lifetime", "Until I turn it off")
        choose("Browser before starting", "Give me a heads-up")
        checkbox("Allow profile Work", True)
        switch("Browser access", True)
        poll(lambda: surfaces()["browser"]["mode"] == "automatic", "Browser automatic")
    choose("Access lifetime", "15 minutes")
    choose("Desktop before starting", "Wait for my approval")
    switch("Desktop access", True)
    poll(lambda: surfaces()["desktop"]["mode"] == "ask", "Desktop ask")
    value = surfaces()
    check("Desktop is On, Wait for approval, timed 15 minutes",
          value["desktop"]["mode"] == "ask" and 800 < value["desktop"]["remainingSeconds"] <= 900,
          desktop=value["desktop"])
    if profile:
        check("Browser is On, heads-up, until stopped, exact profile",
              value["browser"]["mode"] == "automatic" and value["browser"]["remainingSeconds"] is None
              and value["browser"]["profileIds"] == [profile], browser=value["browser"])
    return value


try:
    check("no predecessor endpoint", not endpoint.exists() and not app_pids())
    check("disposable app copy starts as exact sender bytes", digest(app_path) == digest(args.sender))
    sender = identity(app_path)
    incoming = identity(args.incoming)
    note("identities", dict(sender=sender, incoming=incoming,
                            senderSha256=digest(args.sender), incomingSha256=digest(args.incoming)))
    check("sender candidate identity", sender["version"] == args.sender_version and sender["purpose"] == "candidate"
          and sender["sourceRevision"] == args.revision)
    check("incoming candidate identity", incoming["version"] == args.incoming_version
          and incoming["purpose"] == "candidate" and incoming["sourceRevision"] == args.revision)
    serve_feed()
    env = isolated_environment()
    plans.start()
    first = launch(env)
    policies.start()
    check("sender runtime exact source", first["data"]["sourceRevision"] == args.revision)
    check("sender starts with both surfaces Off", all_off(surfaces()))

    profile = url = None
    if args.chrome:
        profile, url = setup_browser()
    else:
        observations["skipped"].append("Browser: no test browser supplied; Desktop-only run")
    before = enable_access(profile)
    note("accessBefore", before)
    if profile:
        task, pre_fence, pre_reference = browser_effects(profile, url, "pre-update")
        close_owner(task)

    # Install and restart stays available while access is live.
    check_for_update()
    check("live access leaves Install and restart enabled", enabled("Install and restart"))
    poll(lambda: "Version " + args.incoming_version + " available." in text() and PAUSE_NOTE in text(),
         "pause and restore note")
    check("Settings explains that access pauses and turns back on", True)

    # A tampered download is refused before access is touched.
    generation = status()["generation"]
    pid = sorted(app_pids())
    started = time.time()
    Feed.mode = "tampered"
    press("Install and restart")
    poll(lambda: "signature" in text().lower(), "tampered signature refusal", 90)
    after = surfaces()
    note("tampered", dict(access=after, generation=status()["generation"], plans=plans.plans(started)))
    check("tampered download leaves app bytes unchanged", digest(app_path) == digest(args.sender))
    check("tampered download never records a resume plan", not plans.plans(started) and plan_absent())
    check("tampered download leaves access On and unchanged", same_access(before, after), before=before, after=after)
    check("tampered download never stops access",
          not policies.saw_off_between(started, time.time()) and "update.access.stopped" not in codes(started),
          diagnostics=diagnostics(started))
    check("tampered download keeps the same runtime", status()["generation"] == generation and sorted(app_pids()) == pid)

    # A replacement that fails after Stop restores the same access at once.
    Feed.mode = "normal"
    if not enabled("Install and restart"):
        check_for_update()
    started = time.time()
    # Fault injection: an unwritable app folder makes the updater's backup
    # rename fail after Stop and prepare_update, before any byte changes.
    app_path.parent.chmod(0o555)
    try:
        press("Install and restart")
        poll(lambda: RESTORED_NOTE in text(), "restored after failed replacement", 90)
    finally:
        app_path.parent.chmod(folder_mode)
    restored = poll(lambda: (value if not all_off(value := surfaces()) and value["desktop"]["mode"] == "ask" else None),
                    "restored access")
    if profile:
        restored = poll(lambda: (value if (value := surfaces())["browser"]["mode"] == "automatic" else None),
                        "restored Browser")
    failed_plans = plans.plans(started)
    note("failedReplacement", dict(access=restored, plans=failed_plans, generation=status()["generation"],
                                   transitions=[e for e in policies.events if e["at"] >= started]))
    check("failed replacement recorded a plan before Stop", bool(failed_plans))
    check("failed replacement stopped, then restored access",
          {"update.access.stopped", "update.install.failed", "update.access.restored"} <= set(codes(started)),
          diagnostics=diagnostics(started), observedOff=policies.saw_off_between(started, time.time()))
    check("failed replacement leaves the sender in place",
          digest(app_path) == digest(args.sender) and status()["generation"] == generation)
    check("failed replacement restores the same access immediately", same_access(before, restored),
          before=before, after=restored)
    check("restoration consumes the plan", poll(plan_absent, "plan removal"))

    # A waiting agent task requires explicit confirmation.
    waiting = owner(["desktop"], wait=False)
    poll(lambda: status()["data"]["admission"]["waiting"] >= 1, "waiting Desktop task")
    note("waitingTask", waiting.status())
    page("Settings")
    if not enabled("Install and restart"):
        check_for_update()
    press("Install and restart")
    poll(lambda: find("Install anyway") and find("Cancel") and CONFIRM_NOTE in text(), "agent-task confirmation")
    check("agent task requires Install anyway", True)
    press("Cancel")
    poll(lambda: not find("Install anyway"), "confirmation dismissed")
    check("Cancel leaves bytes, task, access and plan unchanged",
          digest(app_path) == digest(args.sender) and status()["data"]["admission"]["waiting"] >= 1
          and same_access(before, surfaces()) and plan_absent())

    # Replace with a paused verified download, then restore after relaunch.
    Feed.mode = "pause"
    Feed.started.clear()
    Feed.release.clear()
    started = time.time()
    press("Install and restart")
    press("Install anyway")
    check("verified download begins", Feed.started.wait(60))
    time.sleep(2)
    during = surfaces()
    check("access stays On while the download is incomplete",
          same_access(before, during) and plan_absent() and status()["data"]["admission"]["waiting"] >= 1
          and digest(app_path) == digest(args.sender), during=during)
    released = time.time()
    Feed.release.set()
    poll(lambda: digest(app_path) == digest(args.incoming), "exact signed incoming bytes", 120)
    check("exact signed incoming bytes installed", True)
    fresh = relaunched(generation, "relaunched runtime", started)
    recorded = plans.plans(started)
    plan = recorded[-1]["plan"] if recorded and "plan" in recorded[-1] else {}
    note("plan", dict(events=recorded, releasedAt=released,
                      downloadCompletedAt=next((r.get("completedAt") for r in reversed(Feed.requests)
                                                if r["path"] == DOWNLOAD_PATH), None)))
    note("updatedRuntime", dict(generation=fresh["generation"], previousGeneration=generation,
                                sourceRevision=fresh["data"]["sourceRevision"], identity=identity(app_path)))
    check("updated runtime has a new generation", fresh["generation"] != generation)
    check("updated runtime exact source", fresh["data"]["sourceRevision"] == args.revision)
    check("updated client compiled version", observations["updatedRuntime"]["identity"]["version"] == args.incoming_version)
    check("restart replaces the sender process", not set(app_pids()) & set(pid))
    check("plan written after the verified download", bool(recorded) and recorded[0]["at"] > released)
    check("plan is private to the user", recorded[0].get("mode") == "0o600", mode=recorded[0].get("mode"))
    check("plan binds the incoming version and live surfaces",
          plan.get("schema") == "machine-control-update-resume/v0" and plan.get("targetVersion") == args.incoming_version
          and {e["surface"]: e["mode"] for e in plan.get("surfaces", [])}
          == {name: row["mode"] for name, row in before.items() if row["mode"] != "off"}, plan=plan)
    desktop_plan = next(e for e in plan["surfaces"] if e["surface"] == "desktop")
    check("timed plan keeps the original wall-clock end",
          abs(desktop_plan["expiresAt"] - before["desktop"]["end"]) <= END_TOLERANCE,
          planned=desktop_plan["expiresAt"], original=before["desktop"]["end"])
    if profile:
        browser_plan = next(e for e in plan["surfaces"] if e["surface"] == "browser")
        check("until-stopped plan has no end and exact profiles",
              browser_plan["expiresAt"] is None and browser_plan["profileIds"] == [profile])
    check("sender stopped access only after the verified download",
          "update.access.stopped" in codes(released) and
          all(row["at"] >= released for row in diagnostics(started) if row["operation"] == "update.access.stopped"),
          diagnostics=diagnostics(started), observedOff=policies.saw_off_between(released, time.time()))
    resumed = poll(lambda: (value if (value := surfaces())["desktop"]["mode"] == "ask"
                            and (not profile or value["browser"]["mode"] == "automatic") else None),
                   "updated client restores access", 150)
    note("accessAfter", resumed)
    check("updated client consumes the one-shot plan", poll(plan_absent, "consumed plan", 30))
    check("updated client restores same modes, profiles and original end", same_access(before, resumed),
          before=before, after=resumed)
    poll(lambda: find("Settings"), "updated Settings", 45)
    page("Settings")
    poll(lambda: RESTORED_NOTE in text(), "restored note")
    check("Settings reports access turned back on", True)
    check("updated client records restoration",
          any(row["operation"] == "update.access.restored" and row["version"] == args.incoming_version
              for row in diagnostics(released)), diagnostics=diagnostics(released))
    check("pre-update waiting task ended", status()["data"]["admission"]["waiting"] == 0)
    close_owner(waiting)

    if profile:
        check("test browser survives replacement", chrome.poll() is None)
        poll(lambda: any(row["profileId"] == profile and row.get("connected")
                         for row in status()["data"]["browser"]["profiles"]), "browser reconnects", 60)
        check("test browser profile reconnects to the updated runtime", True)
        # The same fixture document is still loaded in the surviving browser.
        task, post_fence, _ = browser_effects(profile, url + "?after", "post-update", stale=pre_reference)
        # Session fences are per-runtime counters and only usable on the
        # owner's own channel; record whether a pre-update value recurs.
        note("sessionFences", dict(preUpdate=pre_fence, postUpdate=post_fence,
                                   identical=pre_fence == post_fence))
        close_owner(task)
    else:
        observations["skipped"].append("Browser survival, reconnect, effects and pre-update fence: Desktop-only run")

    # Off before replacement stays Off afterwards.
    menu("Stop access")
    poll(lambda: all_off(surfaces()), "tray Stop")
    check("tray Stop turns both surfaces Off", True)
    quit_app()
    check("Quit removes the updated endpoint", True)
    staged = app_path.with_name(app_path.name + ".sender")
    shutil.copyfile(args.sender, staged)
    staged.chmod(app_path.stat().st_mode & 0o777)
    staged.replace(app_path)
    check("sender bytes restored for the Off cycle", digest(app_path) == digest(args.sender))
    second = launch(env)
    generation = second["generation"]
    check("restored sender identity", identity(app_path)["version"] == args.sender_version)
    check("sender relaunch keeps access Off", all_off(surfaces()))
    started = time.time()
    Feed.mode = "normal"
    check_for_update()
    poll(lambda: "Version " + args.incoming_version + " available." in text(), "available note")
    check("Off access has no pause note", PAUSE_NOTE not in text())
    press("Install and restart")
    check("Off access installs without confirmation", not find("Install anyway"))
    poll(lambda: digest(app_path) == digest(args.incoming), "Off-cycle incoming bytes", 120)
    fresh = relaunched(generation, "Off-cycle relaunch", started)
    poll(lambda: find("Settings"), "Off-cycle Settings", 45)
    time.sleep(3)
    check("Off access stays Off after relaunch", all_off(surfaces()))
    check("Off access never records a plan", not plans.plans(started) and plan_absent())
    check("Off access is never stopped or restored",
          not {"update.access.stopped", "update.access.restored"} & set(codes(started)), diagnostics=diagnostics(started))
    page("Settings")
    check("Off cycle reports no restoration", RESTORED_NOTE not in text())
    check("Off-cycle updated source", fresh["data"]["sourceRevision"] == args.revision)
    quit_app()
    check("updated Quit removes the endpoint", True)
except BaseException as error:
    failure = type(error).__name__ + ": " + str(error)
    with contextlib.suppress(Exception):
        (args.output / "failure-ui.private.json").write_text(json.dumps([i for _, i in nodes()], default=str))
    with contextlib.suppress(Exception):
        (args.output / "failure-status.private.json").write_text(json.dumps(plain("status"), default=str))
    raise
finally:
    stop_threads.set()
    Feed.release.set()
    with contextlib.suppress(Exception):
        app_path.parent.chmod(folder_mode)
    for value in list(owners):
        close_owner(value)
    if endpoint.exists() or app_pids():
        with contextlib.suppress(Exception):
            menu("Stop access")
            quit_app()
    for pid in app_pids():
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGTERM)
    if chrome and chrome.poll() is None:
        os.killpg(chrome.pid, signal.SIGTERM)
        try:
            chrome.wait(10)
        except subprocess.TimeoutExpired:
            os.killpg(chrome.pid, signal.SIGKILL)
            chrome.wait(5)
    for server in [*feeds, *([web] if web else [])]:
        server.shutdown()
        server.server_close()
    observations["planEvents"] = plans.events
    observations["policyEvents"] = policies.events
    observations["feedRequests"] = Feed.requests
    log.close()
    report(complete=True)
