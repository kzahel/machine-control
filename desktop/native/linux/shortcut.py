"""Explicit GNOME custom shortcut; preserve unrelated user bindings."""

from gi.repository import Gio, GLib
from pathlib import Path

PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/machine-control-stop/"
KEYS = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM = KEYS + ".custom-keybinding"
BINDING = "<Control><Alt><Shift>period"


class Shortcut:
    def __init__(self, executable):
        path = Path(executable)
        if not path.is_absolute() or not path.is_file():
            raise ValueError("Installed executable required")
        self.command = GLib.shell_quote(str(path)) + " --stop"
        source = Gio.SettingsSchemaSource.get_default()
        self.settings = Gio.Settings.new(KEYS) if source.lookup(KEYS, True) else None
        self.custom = Gio.Settings.new_with_path(CUSTOM, PATH) if source.lookup(CUSTOM, True) else None

    @property
    def available(self):
        return bool(self.settings and self.custom and PATH in self.settings.get_strv("custom-keybindings")
                    and self.custom.get_string("command") == self.command
                    and self.custom.get_string("binding") == BINDING)

    def set(self, enabled):
        if type(enabled) is not bool or not self.settings or not self.custom:
            raise ValueError("GNOME keyboard shortcuts are unavailable")
        entries = list(self.settings.get_strv("custom-keybindings"))
        if self.custom.get_string("command") not in {"", self.command}:
            raise ValueError("This shortcut was changed in GNOME Settings")
        if enabled:
            if not self.custom.set_string("name", "Machine Control — Stop access") or not (
                    self.custom.set_string("command", self.command) and
                    self.custom.set_string("binding", BINDING)):
                raise ValueError("Shortcut settings are not writable")
            if PATH not in entries:
                entries.append(PATH)
        else:
            entries = [v for v in entries if v != PATH]
            for key in ["name", "command", "binding"]:
                self.custom.reset(key)
        if not self.settings.set_strv("custom-keybindings", entries):
            raise ValueError("Shortcut settings are not writable")
        Gio.Settings.sync()
