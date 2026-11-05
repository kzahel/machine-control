"""Private operator preferences, never a grant or a replayable task."""
import json
import os
from pathlib import Path
import stat
import tempfile


class AccessPreferences:
    def __init__(self, root, instance):
        self.root = Path(root)
        self.path = self.root / ('access-preferences-' + instance + '.json')

    def safe(self):
        try: info = self.path.lstat()
        except FileNotFoundError: return
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 2048:
            raise ValueError('Private access preference required')

    def read(self):
        try:
            self.safe()
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream: value = json.loads(stream.read(2049))
            if value.get('schema') == 'machine-control-access-preferences/v1' and isinstance(value.get('preferences'), dict):
                return value['preferences']
        except (OSError, ValueError, TypeError, AttributeError): pass
        return None

    def set(self, preferences):
        self.safe()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=self.root, delete=False) as stream:
                temporary = Path(stream.name); os.fchmod(stream.fileno(), 0o600)
                json.dump(dict(schema='machine-control-access-preferences/v1', preferences=preferences), stream, allow_nan=False)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None: temporary.unlink(missing_ok=True)
