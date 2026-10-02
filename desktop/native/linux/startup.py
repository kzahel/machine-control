"""Owned XDG login entry with a correctly escaped executable argument."""

import os
from pathlib import Path
import stat
import tempfile

MARKER = "X-MachineControl-Owned=org.machine-control.app\n"


def desktop_argument(value):
    if not value or any(ord(c) < 32 for c in value):
        raise ValueError("Choose a stable application path")
    # Exec quoting is parsed after Desktop Entry backslash unescaping.
    value = value.replace("\\", "\\\\\\\\")
    for char in ['"', '`', '$']:
        value = value.replace(char, "\\\\" + char)
    return '"' + value.replace('%', '%%') + '"'


class Startup:
    def __init__(self, executable):
        path = Path(executable)
        if not path.is_absolute() or not path.is_file():
            raise ValueError("Installed executable required")
        self.path = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart/org.machine-control.app.desktop"
        # GIO checks the executable before expanding %% field codes. Use the
        # installed Python runtime as a fixed execv launcher so literal percent
        # signs in the app path work too; the path is only a positional argument.
        launch = "import os,sys; os.execv(sys.argv[1],[sys.argv[1],sys.argv[2]])"
        self.entry = ("[Desktop Entry]\nType=Application\nName=Machine Control\n"
                      "Exec=/usr/bin/python3 -c " + desktop_argument(launch) + " "
                      + desktop_argument(str(path)) + " --background\n"
                      "StartupNotify=false\nTerminal=false\n" + MARKER)

    def owned(self):
        if not self.path.exists() and not self.path.is_symlink():
            return False
        info = self.path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_size > 8192 or MARKER not in self.path.read_text()):
            raise ValueError("Login entry belongs to another application")
        return True

    @property
    def enabled(self):
        try:
            return self.owned() and self.path.read_text() == self.entry
        except (OSError, ValueError):
            return False

    def set(self, enabled):
        if type(enabled) is not bool:
            raise ValueError("Choose a startup preference")
        self.owned()
        if not enabled:
            self.path.unlink(missing_ok=True)
            return
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=self.path.parent, delete=False) as output:
            temporary = Path(output.name)
            os.fchmod(output.fileno(), 0o600)
            output.write(self.entry)
        try:
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
