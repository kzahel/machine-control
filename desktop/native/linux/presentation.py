"""Local operator preferences and CLI; no agent endpoint or GTK dependency."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import stat
import tempfile

PROFILES = {"personal", "minimal", "appliance"}
SCHEMA = "machine-control-presentation/v1"


def instance_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", value):
        raise ValueError("Invalid instance")
    return value


def runtime_directory(instance="desktop"):
    instance_name(instance)
    path = Path(os.environ["XDG_RUNTIME_DIR"]) / ("machine-control-" + instance)
    path.mkdir(mode=0o700, exist_ok=True)
    value = path.lstat()
    if not stat.S_ISDIR(value.st_mode) or value.st_uid != os.getuid() or stat.S_IMODE(value.st_mode) != 0o700:
        raise ValueError("Private runtime directory required")
    return path


class Presentation:
    def __init__(self, instance="desktop", override=None):
        instance_name(instance)
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "machine-control"
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("Private preference directory required")
        self.root = root
        self.path = root / ("presentation.json" if instance == "desktop" else "presentation-" + instance + ".json")
        self.lock = os.open(str(self.path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        info = os.fstat(self.lock)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            os.close(self.lock)
            raise ValueError("Private preference lock required")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self.lock)
            raise ValueError("Live operator is busy; offline editing refused") from None
        self.override = override
        if override is not None and override not in PROFILES:
            raise ValueError("Unknown presentation")
        self.setting = "personal"
        self.diagnostic = None
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                    raise ValueError("Unsafe preference file")
                value = json.loads(stream.read(4097))
                if info.st_size > 4096 or value.get("schema") != SCHEMA or value.get("profile") not in PROFILES:
                    raise ValueError("Invalid preference")
                self.setting = value["profile"]
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, AttributeError):
            self.diagnostic = "Invalid preferences; using Personal"

    def state(self):
        return {"profile": self.override or self.setting, "savedProfile": self.setting, "setting": False,
                "temporaryOverride": self.override is not None, "diagnostic": self.diagnostic}

    def set(self, profile):
        if profile not in PROFILES:
            raise ValueError("Choose personal, minimal or appliance")
        with tempfile.NamedTemporaryFile(mode="w", dir=self.root, delete=False) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            json.dump({"schema": SCHEMA, "profile": profile}, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(temporary, self.path)
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)
        self.setting, self.override, self.diagnostic = profile, None, None
        return self.state()

    def close(self):
        if self.lock is not None:
            os.close(self.lock)
            self.lock = None


def exchange(instance, request):
    endpoint = runtime_directory(instance) / "operator.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(4)
        try:
            client.connect(str(endpoint))
        except (FileNotFoundError, ConnectionRefusedError):
            return None
        client.sendall(json.dumps(request).encode() + b"\n")
        with client.makefile("rb") as reader:
            line = reader.readline(4097)
        if len(line) > 4096 or not line.endswith(b"\n"):
            raise ValueError("Operator response unavailable; command was not replayed")
        return json.loads(line)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["status", "set", "reset"])
    parser.add_argument("profile", nargs="?", choices=sorted(PROFILES))
    parser.add_argument("--instance", default="desktop", type=instance_name)
    args = parser.parse_args()
    if (args.action == "set") != (args.profile is not None):
        parser.error("Only set requires a profile")
    request = {"method": "presentation" if args.action != "status" else "presentation.status",
               "profile": args.profile if args.action == "set" else "personal"}
    try:
        reply = exchange(args.instance, request)
        if reply is None:
            store = Presentation(args.instance)
            try:
                state = store.state() if args.action == "status" else store.set(request["profile"])
                reply = {"ok": True, "presentation": state, "resident": False}
            finally:
                store.close()
        print(json.dumps(reply))
        return 0 if reply.get("ok") else 1
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
