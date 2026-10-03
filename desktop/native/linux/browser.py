"""Grant-scoped Chrome extension relay; references bind both generations."""

import hashlib
import base64
import json
import os
from pathlib import Path
import shutil
import uuid

from gi.repository import Gdk, GLib, Gtk
import artifacts

LIMIT = 1024 * 1024
HOST_NAME = "org.machine_control.browser"
ORIGIN = "chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/"


class Browser:
    def __init__(self, owner):
        self.owner = owner
        self.provider = None
        self.generation = uuid.uuid4().hex
        self.published = None
        self.pending = {}
        self.directory = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "machine-control"
        self.host = self.directory / "browser_host.py"
        self.extension = self.directory / "extension"

    def refresh_owned_installation(self):
        """Refresh an existing opt-in after replacement without opting in again."""
        config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        paths = [config / name / "NativeMessagingHosts" / (HOST_NAME + ".json")
                 for name in ["google-chrome", "google-chrome-for-testing", "chromium"]]
        if any(path.exists() and json.loads(path.read_text()).get("path") == str(self.host)
               for path in paths):
            self.setup(copy_path=False)

    def setup(self, copy_path=True):
        root = Path(__file__).resolve().parent
        self.directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        manifest = {"name": HOST_NAME, "description": "Machine Control browser provider",
                    "path": str(self.host), "type": "stdio", "allowed_origins": [ORIGIN]}
        paths = [config / browser / "NativeMessagingHosts" / (HOST_NAME + ".json")
                 for browser in ["google-chrome", "google-chrome-for-testing", "chromium"]]
        # Refuse to overwrite another installation's registration.
        for path in paths:
            if path.exists() and json.loads(path.read_text()).get("path") != str(self.host):
                raise ValueError("Another Machine Control browser host is registered")
        temporary = self.host.with_suffix(".new")
        shutil.copyfile(root / "browser_host.py", temporary)
        temporary.chmod(0o700)
        temporary.replace(self.host)
        self.extension.mkdir(mode=0o700, exist_ok=True)
        for source in (root / "extension").glob("*"):
            if source.is_file():
                temp = self.extension / (source.name + ".new")
                shutil.copyfile(source, temp)
                temp.replace(self.extension / source.name)
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".new")
            temp.write_text(json.dumps(manifest, indent=2) + "\n")
            temp.chmod(0o600)
            temp.replace(path)
        if copy_path:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(str(self.extension), -1)
        return str(self.extension)

    def trusted(self, pid):
        try:
            args = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            return len(args) >= 3 and Path(os.fsdecode(args[1])) == self.host and (
                os.fsdecode(args[2]) == ORIGIN) and hashlib.sha256(self.host.read_bytes()).digest() == (
                hashlib.sha256((Path(__file__).parent / "browser_host.py").read_bytes()).digest())
        except (OSError, ValueError):
            return False

    def register(self, client, pid):
        if not self.trusted(pid):
            client.close()
            return
        self.disconnect()
        self.provider = client
        self.generation = uuid.uuid4().hex
        self.published = None
        self.send({"type": "registered", "protocolVersion": 1})
        self.sync()

    def send(self, value):
        if not self.provider:
            raise RuntimeError("Browser is not connected")
        frame = json.dumps(value, separators=(",", ":")).encode() + b"\n"
        if len(frame) > LIMIT:
            raise ValueError("Browser frame exceeds 1 MiB")
        try:
            self.provider.sendall(frame)
        except OSError:
            self.disconnect()
            raise RuntimeError("Browser disconnected") from None

    def sync(self):
        if not self.provider:
            return
        grant = self.owner.grants
        state = (grant.generation, grant.authorize("browser.tabs") is None,
                 grant.authorize("browser.eval") is None)
        if state != self.published:
            self.published = state
            try:
                self.send({"type": "grant", "browser": False, "devtools": False})
                self.send({"type": "grant", "browser": state[1], "devtools": state[2]})
            except RuntimeError:
                return
            # Discard in-flight authority on a generation transition.
            for identifier, item in list(self.pending.items()):
                if item["grant"] != state[0]:
                    self.complete(identifier, {"ok": False, "errorCode": "stale_generation"})

    def execute(self, request, finish):
        self.sync()
        if not self.provider:
            finish(self.owner.provider.fail(request, request["operation"], "browser_provider_unavailable", "Connect the extension"))
            return
        grant = self.owner.grants.generation
        params = {k: v for k, v in request.items() if k not in {
            "operation", "requestId", "generation", "expectedGeneration"}}
        if "reference" in params:
            prefix = grant + ":" + self.generation + ":"
            if not isinstance(params["reference"], str) or not params["reference"].startswith(prefix):
                finish(self.owner.provider.fail(request, request["operation"], "stale_reference", "Observe again"))
                return
            params["reference"] = params["reference"][len(prefix):]
        identifier = uuid.uuid4().hex
        self.pending[identifier] = {"request": request, "finish": finish, "grant": grant,
                                    "provider": self.generation}
        try:
            self.send({"type": "request", "id": identifier, "operation": request["operation"], "params": params})
        except (RuntimeError, ValueError):
            self.complete(identifier, {"ok": False, "errorCode": "browser_provider_unavailable"})
        GLib.timeout_add_seconds(30, lambda: self.complete(identifier, {"ok": False, "errorCode": "browser_timeout"}))

    def message(self, client, frame):
        if client != self.provider:
            return
        if frame.get("type") == "response" and isinstance(frame.get("id"), str):
            self.complete(frame["id"], frame)

    def complete(self, identifier, frame):
        item = self.pending.pop(identifier, None)
        if not item:
            return False
        request = item["request"]
        error = self.owner.grants.authorize(request["operation"], item["grant"])
        if item["provider"] != self.generation:
            error = "browser_provider_unavailable"
        if frame.get("ok") is not True:
            error = error or frame.get("errorCode", "browser_operation_failed")
        if error:
            result = self.owner.provider.fail(request, request["operation"], error, "Browser operation refused")
            result.update(actualRoute="user/chrome-extension/cdp", delivery="unknown", effect="unknown",
                          uncertainty="authority_or_provider_changed_after_dispatch", retrySafety="unsafe_delivery_unknown")
        else:
            result = self.owner.provider.envelope(request, request["operation"])
            result.update(actualRoute="user/chrome-extension/cdp", fidelity="chromium_tab_cdp",
                          delivery="confirmed", effect="unverifiable", uncertainty="no_independent_state_change")
            result["data"] = frame.get("data", {})
            if request["operation"] == "browser.capture":
                try:
                    data = base64.b64decode(result["data"].pop("png"), validate=True)
                    result["data"]["artifact"] = artifacts.write(data)
                except (KeyError, ValueError):
                    result = self.owner.provider.fail(request, request["operation"], "invalid_capture", "Invalid browser capture")
            if request["operation"] == "browser.snapshot":
                for element in result["data"].get("elements", []):
                    if "reference" in element:
                        element["reference"] = item["grant"] + ":" + self.generation + ":" + element["reference"]
        item["finish"](result)
        return False

    def disconnect(self, client=None):
        if client is not None and client != self.provider:
            return
        if self.provider:
            self.provider.close()
        self.provider = None
        self.generation = uuid.uuid4().hex
        self.published = None
        for identifier in list(self.pending):
            self.complete(identifier, {"ok": False, "errorCode": "browser_provider_unavailable"})
