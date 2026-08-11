#!/usr/bin/env bash
# Collect a read-only ChromeOS testbed diagnostic bundle.

set -uo pipefail

. "$(dirname "$0")/common.sh"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$REPO_DIR/bin/chromeos"
OUTPUT_FORMAT="${CHROMEOS_OUTPUT:-text}"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
output="${1:-/tmp/chromeos-testbed-diagnostics-$timestamp}"

if [[ -e "$output" ]]; then
    echo "Refusing to overwrite existing diagnostics path: $output" >&2
    exit 1
fi
mkdir -p "$output"
output=$(cd "$output" && pwd)

captures=()

capture() {
    local name="$1"
    shift
    local file="$output/$name"
    local rc=0
    if "$@" >"$file" 2>&1; then
        rc=0
    else
        rc=$?
    fi
    captures+=("$name" "$rc")
}

capture doctor.txt env CHROMEOS_OUTPUT=text "$REPO_DIR/scripts/doctor.sh"
capture doctor.json env CHROMEOS_OUTPUT=json "$REPO_DIR/scripts/doctor.sh"
capture info.json "$CLI" --json info
capture targets.json "$CLI" --json targets
capture desktop-tree.json "$CLI" --json desktop-tree --depth 4
capture adb.json "$CLI" --json adb-status
capture power.json "$CLI" --json power-status
capture device.txt ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; \
echo '[release]'; cat /etc/lsb-release 2>/dev/null || true; \
echo '[kernel]'; uname -a; \
echo '[uptime]'; uptime; \
echo '[root-device]'; rootdev -s 2>/dev/null || true; \
echo '[mounts]'; mount | grep -E ' on /( |usr|mnt/stateful_partition)' || true; \
echo '[chrome-flags]'; cat /etc/chrome_dev.conf 2>/dev/null || true; \
echo '[sshd]'; ps -ef | grep '[s]shd' || true; \
echo '[input-devices]'; cat /proc/bus/input/devices 2>/dev/null || true; \
echo '[adb]'; adb devices -l 2>/dev/null || true"

screenshot_rc=0
if "$CLI" --json screenshot "$output/screenshot.jpg" >"$output/screenshot.json" 2>&1; then
    screenshot_rc=0
else
    screenshot_rc=$?
fi
captures+=("screenshot.json" "$screenshot_rc")

python3 - "$output/manifest.json" "$SSH_HOST" "${captures[@]}" <<'PY'
import datetime
import json
import os
import sys

manifest_path, host = sys.argv[1], sys.argv[2]
fields = sys.argv[3:]
captures = []
for i in range(0, len(fields), 2):
    name, rc = fields[i], int(fields[i + 1])
    path = os.path.join(os.path.dirname(manifest_path), name)
    captures.append({
        "name": name,
        "ok": rc == 0,
        "exit_code": rc,
        "bytes": os.path.getsize(path) if os.path.exists(path) else 0,
    })
manifest = {
    "schema_version": 1,
    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "host": host,
    "captures": captures,
}
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
    f.write("\n")
PY

if [[ "$OUTPUT_FORMAT" == "json" ]]; then
    python3 -c "
import json,sys
manifest=json.load(open(sys.argv[2], encoding='utf-8'))
print(json.dumps({'ok':True,'directory':sys.argv[1],
                  'manifest':sys.argv[2],'captures':manifest['captures']}))
" "$output" "$output/manifest.json"
else
    echo "Diagnostics saved to $output"
    echo "Manifest: $output/manifest.json"
fi
