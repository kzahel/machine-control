"""Exercise the installed ACL as an ordinary Windows process."""

import ctypes
from ctypes import wintypes
from pathlib import Path
import sys


class Luid(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.LONG)]


class TokenPrivileges(ctypes.Structure):
    _fields_ = [("count", wintypes.DWORD), ("luid", Luid), ("attributes", wintypes.DWORD)]


def disable_backup_and_restore():
    # SSH and some runner tokens have these privileges enabled. Native
    # directory creation can use them to bypass the ACL under test.
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.LookupPrivilegeValueW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(Luid)]
    advapi.AdjustTokenPrivileges.argtypes = [
        wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(TokenPrivileges), wintypes.DWORD,
        ctypes.c_void_p, ctypes.c_void_p,
    ]

    token_adjust_privileges = 0x20
    error_not_all_assigned = 1300
    token = wintypes.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), token_adjust_privileges, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        for name in ("SeBackupPrivilege", "SeRestorePrivilege"):
            luid = Luid()
            if not advapi.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
                raise ctypes.WinError(ctypes.get_last_error())
            state = TokenPrivileges(1, luid, 0)
            adjusted = advapi.AdjustTokenPrivileges(token, False, ctypes.byref(state), 0, None, None)
            error = ctypes.get_last_error()
            if not adjusted or error not in (0, error_not_all_assigned):
                raise ctypes.WinError(error)
    finally:
        kernel.CloseHandle(token)


def main():
    client = Path(sys.argv[1])
    disable_backup_and_restore()
    cache = client / "__pycache__"
    try:
        cache.mkdir()
    except PermissionError:
        pass
    else:
        raise AssertionError("Ordinary Python created a protected cache directory")

    sys.path.insert(0, str(client))
    import fixture

    assert fixture.value == 1, "Python could not read protected source"
    assert not cache.exists(), "Python import created a protected cache directory"


if __name__ == "__main__":
    main()
