"""Installer-owned user PATH entry; never pass PATH through NSIS string buffers."""
import ctypes
import hashlib
import ntpath
import sys

STATE = r"Software\MachineControl\CommandPath"


def normalized(value, expand=False):
    value = value.strip().strip('"')
    return ntpath.normcase(ntpath.normpath(ntpath.expandvars(value) if expand else value))


def change(value, directory, enabled, owned, *, expand=False):
    """Preserve unrelated entries byte-for-byte and never adopt a user's entry."""
    entries = value.split(";") if value else []
    matches = [i for i, entry in enumerate(entries) if normalized(entry, expand) == normalized(directory)]
    if enabled:
        if matches:
            return value, owned
        return value + (";" if value else "") + directory, True
    if owned and matches:
        # Only our exact spelling is owned. A user-rewritten equivalent stays.
        try:
            entries.remove(directory)
        except ValueError:
            pass
        return ";".join(entries), False
    return value, False


def apply(directory, operation):
    import winreg
    directory = ntpath.abspath(directory)
    if ";" in directory:
        raise ValueError("Installation paths containing semicolons cannot be registered in PATH")
    key_name = STATE + "\\" + hashlib.sha256(normalized(directory).encode()).hexdigest()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_name) as state:
        try:
            owned = winreg.QueryValueEx(state, "Owned")[0] == 1
        except FileNotFoundError:
            owned = False
        try:
            originally_absent = winreg.QueryValueEx(state, "PathWasAbsent")[0] == 1
        except FileNotFoundError:
            originally_absent = False
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as environment:
            existed = True
            try:
                value, kind = winreg.QueryValueEx(environment, "Path")
            except FileNotFoundError:
                value, kind, existed = "", winreg.REG_EXPAND_SZ, False
            if kind not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) or not isinstance(value, str):
                raise ValueError("User PATH has an unsupported registry type")
            was_owned = owned
            updated, owned = change(value, directory, operation == "enable", owned,
                                    expand=kind == winreg.REG_EXPAND_SZ)
            if owned and not was_owned:
                originally_absent = not existed
            if updated != value:
                if updated or not originally_absent:
                    winreg.SetValueEx(environment, "Path", 0, kind, updated)
                elif existed:
                    winreg.DeleteValue(environment, "Path")
            winreg.SetValueEx(state, "Owned", 0, winreg.REG_DWORD, int(owned))
            winreg.SetValueEx(state, "PathWasAbsent", 0, winreg.REG_DWORD,
                             int(originally_absent))
    if operation == "remove":
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_name)
    # Broadcast with a bounded wait; it cannot refresh every existing process.
    result = ctypes.c_size_t()
    notify = ctypes.windll.user32.SendMessageTimeoutW
    notify.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t,
                       ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_uint,
                       ctypes.POINTER(ctypes.c_size_t)]
    notify(0xffff, 0x001A, 0, "Environment", 0x0002, 2000, ctypes.byref(result))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3 or sys.argv[1] not in {"enable", "disable", "remove"}:
            raise ValueError("Expected enable|disable|remove INSTALL_DIRECTORY")
        apply(sys.argv[2], sys.argv[1])
    except (OSError, ValueError) as error:
        print(f"Machine Control PATH registration failed: {error}", file=sys.stderr)
        raise SystemExit(1)
