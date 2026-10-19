#!/usr/bin/env python3
"""Install only the owned screensaver assets; never edit a live Steam VDF."""

import json
import math
import os
from pathlib import Path
import sys
import tempfile


DEFAULTS = {"mode": "ball", "size": 32, "brightness": 10, "speed": 40}
ASSETS = {"index.html", "main.js", "main.css"}


def validate(config):
    if set(config) != set(DEFAULTS) or config["mode"] not in {"black", "ball"}:
        raise ValueError("invalid screensaver configuration")
    for key, low, high in (("size", 1, 512), ("brightness", 0, 100), ("speed", 1, 200)):
        value = config[key]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not low <= value <= high
        ):
            raise ValueError(f"{key} must be between {low} and {high}")
    return config


def atomic_write(path, content):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f"refusing non-regular screensaver file: {path.name}")
    fd, temporary = tempfile.mkstemp(prefix=".quiet-ball-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply(request, steam_root):
    action = request["action"]
    if action not in {"install", "configure", "status"}:
        raise ValueError("unsupported screensaver action")
    if not steam_root.is_dir():
        raise ValueError("Steam root is unavailable")
    root = steam_root.resolve()
    relative = Path("config/uioverrides/screensavers/quiet-ball")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("refusing a linked screensaver directory")
    destination = root / relative
    config_path = destination / "config.json"
    if config_path.is_symlink():
        raise ValueError("refusing linked screensaver configuration")
    installed = destination.is_dir() and all((destination / name).is_file() for name in ASSETS)
    if action == "status":
        return {
            "installed": installed,
            "settings": validate(json.loads(config_path.read_text())) if config_path.exists() else None,
            "selection": "Inspect Steam Settings > Customization; file presence does not prove activation",
        }
    if action == "configure" and not installed:
        raise ValueError("install the screensaver before configuring it")
    patch = request.get("settings", {})
    if not isinstance(patch, dict) or set(patch) - set(DEFAULTS):
        raise ValueError("unknown screensaver setting")
    settings = dict(DEFAULTS)
    if config_path.exists():
        settings.update(validate(json.loads(config_path.read_text())))
    settings.update(patch)
    validate(settings)
    if action == "install":
        assets = request["assets"]
        if set(assets) != ASSETS or not all(isinstance(v, str) for v in assets.values()):
            raise ValueError("unexpected screensaver assets")
        # Validate every destination before replacing any asset.
        for name in ASSETS:
            path = destination / name
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise ValueError("refusing a non-regular screensaver asset")
        destination.mkdir(parents=True, exist_ok=True)
        # Configuration precedes the entry page, which acts as the install marker.
        atomic_write(config_path, json.dumps(settings, indent=2) + "\n")
        for name in ("main.css", "main.js", "index.html"):
            atomic_write(destination / name, assets[name])
    else:
        atomic_write(config_path, json.dumps(settings, indent=2) + "\n")
    return {
        "installed": True,
        "settings": settings,
        "selection": "Select quiet-ball in Steam Settings > Customization and configure the idle timer",
    }


if __name__ == "__main__":
    try:
        request = json.load(sys.stdin)
        print(json.dumps(apply(request, Path.home() / ".steam/root")))
    except (KeyError, ValueError, OSError, TypeError) as error:
        print(f"steamdeck screensaver: {error}", file=sys.stderr)
        sys.exit(1)
