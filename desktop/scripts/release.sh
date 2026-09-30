#!/usr/bin/env bash
# A tagged desktop publication uses the protected main-only workflow.
set -euo pipefail
if [[ $# -ne 1 || ! "$1" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
  echo 'Usage: desktop/scripts/release.sh MAJOR.MINOR.PATCH' >&2
  exit 1
fi
version="$1"
tag="desktop-v$version"
cd "$(dirname "$0")/../.."
if [[ "$(git branch --show-current)" != main || -n "$(git status --porcelain)" ]]; then
  echo 'Release from a clean main checkout.' >&2
  exit 1
fi
if [[ "$(gh repo view --json nameWithOwner --jq .nameWithOwner)" != kzahel/machine-control ]]; then
  echo 'Expected the Machine Control origin repository.' >&2
  exit 1
fi
git fetch origin main --tags
if [[ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]]; then
  echo 'Local main must match origin/main.' >&2
  exit 1
fi
if git show-ref --verify --quiet "refs/tags/$tag"; then
  echo 'Tag already exists; never replace a release tag.' >&2
  exit 1
fi
python3 desktop/scripts/release.py preflight "$version"
git tag -a "$tag" -m "Machine Control desktop $version"
git push origin "refs/tags/$tag"
if ! gh workflow run macos-desktop.yml --ref main -f "version=$version" -f "release_tag=$tag"; then
  echo "Tag pushed. Retry dispatch with: gh workflow run macos-desktop.yml --ref main -f version=$version -f release_tag=$tag" >&2
  exit 1
fi
echo "Dispatched $tag: checks → signed Mac builds → verified draft → publication."
echo 'Verify the workflow, published assets, and https://machinecontrol.dev/downloads/.'
