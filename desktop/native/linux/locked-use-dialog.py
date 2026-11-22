#!/usr/bin/python3
"""Native opt-in dialog. The password only travels into the root helper pipe."""

import ctypes
import json
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk


HELPER = "/usr/lib/machine-control/locked-runtime/locked-credential.py"


def main(action):
    # Block same-UID inspection of this dialog's memory and pipe handles.
    if ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0) != 0:
        return {"accepted": False, "errorCode": "native_password_dialog_unavailable"}
    if action not in ("setup", "remove"):
        return {"accepted": False, "errorCode": "invalid_locked_use_setup"}
    GLib.set_prgname("machine-control-locked-setup")
    GLib.set_application_name("Machine Control Covered Desktop Setup")
    removing = action == "remove"
    dialog = Gtk.Dialog(title="Remove covered access" if removing else "Set up covered desktop access",
                        modal=True)
    dialog.set_default_size(460, -1)
    dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
    dialog.add_button("Remove" if removing else "Continue", Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.OK)
    area = dialog.get_content_area()
    area.set_border_width(16)
    area.set_spacing(12)
    label = Gtk.Label(label=(
        "Remove the saved password and disable tasks that unlock this desktop?"
        if removing else
        "Enter your Ubuntu account password. Machine Control saves an encrypted copy in a privileged helper "
        "so approved tasks can unlock behind a screen cover. Local input and Stop relock the desktop."
    ), xalign=0)
    label.set_line_wrap(True)
    label.set_max_width_chars(48)
    area.add(label)
    entry = None
    if not removing:
        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        entry.set_activates_default(True)
        entry.set_max_length(4096)
        entry.set_placeholder_text("Ubuntu account password")
        entry.get_accessible().set_name("Ubuntu account password")
        area.add(entry)
        dialog.set_focus(entry)
    dialog.show_all()
    if dialog.run() != Gtk.ResponseType.OK:
        dialog.destroy()
        return {"accepted": False, "errorCode": "cancelled"}
    password = b""
    if entry is not None:
        password = entry.get_text().encode("utf-8")
        entry.set_text("")
    dialog.destroy()
    if not removing and (not 1 <= len(password) <= 4096 or any(c in password for c in b"\x00\r\n")):
        return {"accepted": False, "errorCode": "unlock_credential_invalid"}
    reply = subprocess.run(
        ["/usr/bin/pkexec", "/usr/bin/python3", "-I", "-B", HELPER, action],
        input=password + b"\n" if not removing else b"",
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120,
    )
    value = json.loads(reply.stdout) if len(reply.stdout) <= 2048 else {}
    if reply.returncode == 0 and value.get("accepted") is True:
        return {"accepted": True}
    if value.get("errorCode") == "locked_credential_rejected":
        return {"accepted": False, "errorCode": "unlock_credential_invalid"}
    return {"accepted": False, "errorCode": "locked_use_setup_refused"}


if __name__ == "__main__":
    try:
        result = main(sys.argv[1])
    except (IndexError, OSError, ValueError, subprocess.SubprocessError):
        result = {"accepted": False, "errorCode": "locked_use_setup_refused"}
    print(json.dumps(result), flush=True)
