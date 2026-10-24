#!/usr/bin/env bash
# A tagged desktop publication uses the protected main-only workflow.
set -euo pipefail
if [[ $# -lt 1 || $# -gt 3 || ! "$1" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
  echo 'Usage: desktop/scripts/release.sh MAJOR.MINOR.PATCH [CANDIDATE_RUN_ID ACCEPTANCE_JSON]' >&2
  exit 1
fi
version="$1"
tag="desktop-v$version"
candidate_run="${2:-}"
acceptance_file="${3:-}"
acceptance=''
if [[ -n "$acceptance_file" && -z "$candidate_run" ]]; then
  echo 'An acceptance receipt requires its exact candidate run.' >&2
  exit 1
fi
if python3 - "$version" <<'PY'
import sys
sys.exit(0 if tuple(map(int,sys.argv[1].split('.'))) >= (0,6,9) else 1)
PY
then
  if [[ -z "$candidate_run" || -z "$acceptance_file" ]]; then
    echo 'New releases require an accepted exact candidate and packaged VM receipt.' >&2
    exit 1
  fi
fi
if [[ -n "$acceptance_file" ]]; then
  acceptance_file="$(python3 -c 'import pathlib,sys;print(pathlib.Path(sys.argv[1]).resolve(strict=True))' "$acceptance_file")"
fi
if [[ -n "$candidate_run" && ! "$candidate_run" =~ ^[1-9][0-9]*$ ]]; then
  echo 'Expected a numeric unified candidate workflow run ID.' >&2
  exit 1
fi
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
if [[ -n "$candidate_run" ]]; then
  receipt="$(mktemp)"
  trap 'rm -f "$receipt"' EXIT
  gh api "repos/kzahel/machine-control/actions/runs/$candidate_run" > "$receipt"
  candidate_identity="$(python3 desktop/scripts/release.py check-run "$receipt" --revision "$(git rev-parse HEAD)" --id "$candidate_run")"
  if [[ -n "$acceptance_file" ]]; then
    python3 desktop/scripts/packaged-acceptance.py "$acceptance_file" --revision "$(git rev-parse HEAD)" --version "$version" --run "$candidate_identity"
    acceptance="$(python3 -c 'import json,sys;print(json.dumps(json.load(open(sys.argv[1])),separators=(",",":")))' "$acceptance_file")"
  fi
fi
git tag -a "$tag" -m "Machine Control desktop $version"
git push origin "refs/tags/$tag"
if ! gh workflow run desktop-release.yml --ref main -f "version=$version" -f "release_tag=$tag" -f "candidate_run=$candidate_run" -f "macos_acceptance=$acceptance"; then
  echo "Tag pushed. Retry the original workflow dispatch with version=$version, release_tag=$tag, candidate_run=$candidate_run and the same macos_acceptance receipt." >&2
  exit 1
fi
echo "Dispatched $tag: checks → signed platform builds → verified draft → publication."
echo 'CI publishes automatically after all checks pass; no monitoring is required.'
echo 'Workflow: https://github.com/kzahel/machine-control/actions/workflows/desktop-release.yml'
