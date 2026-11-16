"""Prevent accidental writes to the installed Mac Python payload.

Deletion/rename and ACL administration remain available to the owner/updater.
This is an accident guard, not containment from a same-user shell.
"""
import os
from pathlib import Path
import subprocess
import sys


def protect(root):
    if sys.platform != "darwin":
        return  # Linux packages are root-owned or mounted read-only.
    root = Path(root)
    if not (root / "client-runtime.json").is_file():
        raise ValueError("Installed CLI identity is missing")
    if root.is_symlink():
        raise ValueError("Installed CLI must not contain links")
    if not os.access(root, os.W_OK):
        return  # Already protected or owned by another installation identity.
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("Installed CLI must not contain links")
    # On directories write/append mean add_file/add_subdirectory. Do not
    # deny delete/delete_child: whole-app replacement and cleanup need them.
    subprocess.run(["/bin/chmod", "-R", "+a", "everyone deny write,append", str(root)],
                   check=True)


if __name__ == "__main__":
    protect(Path(__file__).resolve().parent)
