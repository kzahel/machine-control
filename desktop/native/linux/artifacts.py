"""Bounded private capture artifacts shared by desktop and browser providers."""

import hashlib
import os
from pathlib import Path
import stat
import struct
import uuid


def write(data):
    if not isinstance(data, bytes) or not data.startswith(b"\x89PNG\r\n\x1a\n") or not 24 <= len(data) <= 16 * 1024 * 1024:
        raise ValueError("Invalid PNG artifact")
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "machine-control/desktop/artifacts"
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    value = root.lstat()
    if not stat.S_ISDIR(value.st_mode) or value.st_uid != os.getuid() or stat.S_IMODE(value.st_mode) != 0o700:
        raise ValueError("Private artifact directory required")
    # A fixed count bounds this profile's disk use; no unrelated file is removed.
    entries = sorted((p for p in root.glob("*.png") if len(p.stem) == 36),
                     key=lambda p: p.lstat().st_mtime)
    for entry in entries[:-63]:
        entry.unlink()
    identifier = str(uuid.uuid4())
    path = root / (identifier + ".png")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
    width, height = struct.unpack(">II", data[16:24])
    return {"id": identifier, "guestPath": str(path), "width": width, "height": height,
            "mediaType": "image/png", "byteLength": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}
