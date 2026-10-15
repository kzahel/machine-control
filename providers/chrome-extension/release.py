#!/usr/bin/env python3
"""Tag a Chrome Web Store release of the Machine Control extension.

    providers/chrome-extension/release.py VERSION

Run from a clean, current main after committing the CHANGELOG entry. The
script bumps manifest.json when VERSION is newer (or keeps an already
prepared untagged version), commits, and atomically pushes main and
extension-vVERSION. CI then tests, packages and submits the exact ZIP
(.github/workflows/chrome-extension.yml); Google still reviews.
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True,
                          capture_output=True, text=True).stdout.strip()


def parts(version: str) -> tuple[int, ...]:
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version):
        sys.exit(f"Invalid version {version!r}")
    return tuple(int(part) for part in version.split("."))


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    version = sys.argv[1]
    tag = f"extension-v{version}"
    if git("branch", "--show-current") != "main":
        sys.exit("Release from main")
    if git("status", "--porcelain"):
        sys.exit("Commit working-tree changes before releasing")
    if git("tag", "--list", tag) or git("ls-remote", "--tags", "origin", f"refs/tags/{tag}"):
        sys.exit(f"{tag} already exists")
    manifest_path = ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if parts(version) < parts(manifest["version"]):
        sys.exit("Choose a version at least the current extension version")
    if f"## [{version}]" not in (ROOT / "CHANGELOG.md").read_text():
        sys.exit("Add and commit the CHANGELOG entry first")
    git("fetch", "origin", "main")
    subprocess.run(["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"],
                   cwd=REPO, check=True)
    if parts(version) > parts(manifest["version"]):
        manifest["version"] = version
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        git("add", str(manifest_path))
        git("commit", "-m", f"Release Machine Control Chrome extension {version}")
    git("tag", tag)
    subprocess.run(["git", "push", "--atomic", "origin", "HEAD:main", f"refs/tags/{tag}"],
                   cwd=REPO, check=True)
    print(f"Queued {tag} at {git('rev-parse', 'HEAD')}: "
          "https://github.com/kzahel/machine-control/actions/workflows/chrome-extension.yml")


if __name__ == "__main__":
    main()
