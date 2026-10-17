"""Persistent local choice; does not contain or restore a grant."""
import json
import os
from pathlib import Path
import stat
import tempfile


class BrowserPreference:
    def __init__(self, root, instance):
        self.root = Path(root)
        self.path = self.root / ("browser-while-locked-" + instance + ".json")
        self.enabled = False
        try:
            self._safe()
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                value = json.loads(stream.read(1025))
            self.enabled = value.get("schema") == "machine-control-browser-locked/v1" and value.get("enabled") is True
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def _safe(self):
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 1024:
            raise ValueError("Private browser preference required")

    def set(self, enabled):
        if type(enabled) is not bool:
            raise ValueError("Choose browser access while locked")
        self._safe()
        with tempfile.NamedTemporaryFile(mode="w", dir=self.root, delete=False) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            json.dump({"schema": "machine-control-browser-locked/v1", "enabled": enabled}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(temporary, self.path)
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            self.enabled = enabled
        finally:
            temporary.unlink(missing_ok=True)
