#!/usr/bin/env bash
# End-to-end ChromeOS testbed smoke test with UI restoration.

set -uo pipefail

. "$(dirname "$0")/common.sh"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$REPO_DIR/bin/chromeos"
OUTPUT_FORMAT="${CHROMEOS_OUTPUT:-text}"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
output="/tmp/chromeos-testbed-smoke-$timestamp"
run_ui=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-ui) run_ui=0; shift ;;
        --output) output="$2"; shift 2 ;;
        *) output="$1"; shift ;;
    esac
done

if [[ -e "$output" ]]; then
    echo "Refusing to overwrite existing smoke-test path: $output" >&2
    exit 1
fi
mkdir -p "$output"
output=$(cd "$output" && pwd)

steps=()
passed=0
failed=0
quick_settings_open=0
settings_open=0
settings_preexisting=0

say() {
    [[ "$OUTPUT_FORMAT" != "json" ]] && echo "$*"
}

record() {
    local name="$1" status="$2" detail="${3:-}"
    steps+=("$name" "$status" "$detail")
    if [[ "$status" == "passed" ]]; then
        ((passed++))
        say "[OK]   $name"
    elif [[ "$status" == "skipped" ]]; then
        say "[SKIP] $name${detail:+ — $detail}"
    else
        ((failed++))
        say "[FAIL] $name${detail:+ — $detail}"
    fi
}

capture_step() {
    local name="$1" file="$2"
    shift 2
    if "$@" >"$output/$file" 2>&1; then
        record "$name" passed
        return 0
    fi
    local rc=$?
    record "$name" failed "exit $rc; see $file"
    return "$rc"
}

restore_ui() {
    if (( ! settings_preexisting )); then
        local visible
        visible=$("$CLI" --json desktop-find '^Settings$' --role window 2>/dev/null || true)
        if [[ -n "$visible" ]] && python3 -c "
import json,sys
try: raise SystemExit(0 if json.loads(sys.argv[1]).get('count',0) > 0 else 1)
except Exception: raise SystemExit(1)
" "$visible"; then
            settings_open=1
            quick_settings_open=0
        fi
    fi
    if (( settings_open )); then
        "$CLI" shortcut ctrl shift w >/dev/null 2>&1 || true
        if ! "$CLI" --json desktop-wait '^Settings$' --role window --absent --timeout 5 \
            >"$output/wait-settings-closed.json" 2>&1; then
            "$CLI" desktop-action '^Settings$' focus --role window >/dev/null 2>&1 || true
            "$CLI" shortcut ctrl shift w >/dev/null 2>&1 || true
            "$CLI" --json desktop-wait '^Settings$' --role window --absent --timeout 5 \
                >"$output/wait-settings-closed-retry.json" 2>&1 || return 1
        fi
        settings_open=0
    elif (( quick_settings_open )); then
        "$CLI" shortcut escape >/dev/null 2>&1 || true
        "$CLI" --json desktop-wait '^Settings$' --role button --absent --timeout 5 \
            >"$output/wait-quick-settings-closed.json" 2>&1 || return 1
        quick_settings_open=0
    fi
    return 0
}
trap restore_ui EXIT INT TERM

say "Running ChromeOS smoke test against $SSH_HOST..."

capture_step "Infrastructure health" doctor.json \
    env CHROMEOS_OUTPUT=json "$REPO_DIR/scripts/doctor.sh" || true
capture_step "Input client and device discovery" info.json \
    "$CLI" --json info || true
capture_step "Browser target discovery" targets.json \
    "$CLI" --json targets || true
capture_step "Desktop accessibility tree" desktop-tree.json \
    "$CLI" --json desktop-tree --depth 3 || true
capture_step "Baseline screenshot" baseline.json \
    "$CLI" --json screenshot "$output/baseline.jpg" || true

touch_available=0
if [[ -s "$output/info.json" ]] && python3 - "$output/info.json" <<'PY'
import json
import sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
touch = r.get("touch_max") or []
raise SystemExit(0 if len(touch) == 2 and touch[0] and touch[1] else 1)
PY
then
    touch_available=1
fi

settings_matches=$("$CLI" --json desktop-find '^Settings$' --role window 2>/dev/null || true)
if [[ -n "$settings_matches" ]] && python3 -c "
import json,sys
try:
    raise SystemExit(0 if json.loads(sys.argv[1]).get('count',0) > 0 else 1)
except Exception:
    raise SystemExit(1)
" "$settings_matches"; then
    settings_preexisting=1
fi

if (( run_ui )); then
    if "$CLI" shortcut alt shift s >"$output/open-quick-settings.json" 2>&1; then
        quick_settings_open=1
        if "$CLI" --json desktop-wait '^Settings$' --role button --timeout 8 \
            >"$output/wait-quick-settings.json" 2>&1; then
            record "Keyboard opens Quick Settings" passed
            capture_step "Quick Settings screenshot" quick-settings.json \
                "$CLI" --json screenshot "$output/quick-settings.jpg" || true

            if (( settings_preexisting )); then
                record "Calibrated touchscreen opens Settings" skipped \
                    "Settings was already open; preserving initial UI state"
            elif (( touch_available )); then
                if "$CLI" --json desktop-tap '^Settings$' --role button \
                    >"$output/tap-settings.json" 2>&1; then
                    if "$CLI" --json desktop-wait '^Settings$' --role window --timeout 10 \
                        >"$output/wait-settings.json" 2>&1; then
                        settings_open=1
                        quick_settings_open=0
                        record "Calibrated touchscreen opens Settings" passed
                        capture_step "Settings screenshot" settings.json \
                            "$CLI" --json screenshot "$output/settings.jpg" || true
                    else
                        record "Calibrated touchscreen opens Settings" failed \
                            "tap sent but Settings target did not appear"
                    fi
                else
                    record "Calibrated touchscreen opens Settings" failed \
                        "see tap-settings.json"
                fi
            else
                record "Calibrated touchscreen opens Settings" skipped \
                    "no built-in touchscreen detected"
            fi
        else
            record "Keyboard opens Quick Settings" failed \
                "Settings button did not become visible"
        fi
    else
        record "Keyboard opens Quick Settings" failed "shortcut failed"
    fi
else
    record "Interactive UI checks" skipped "--no-ui requested"
fi

if restore_ui; then
    record "UI state restored" passed
else
    record "UI state restored" failed "see wait-*-closed.json"
fi
trap - EXIT INT TERM
capture_step "Restored-state screenshot" restored.json \
    "$CLI" --json screenshot "$output/restored.jpg" || true

python3 - "$output/manifest.json" "$SSH_HOST" "$passed" "$failed" "${steps[@]}" <<'PY'
import datetime
import json
import sys

path, host, passed, failed = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
fields = sys.argv[5:]
steps = []
for i in range(0, len(fields), 3):
    name, status, detail = fields[i:i + 3]
    item = {"name": name, "status": status}
    if detail:
        item["detail"] = detail
    steps.append(item)
manifest = {
    "schema_version": 1,
    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "host": host,
    "ok": failed == 0,
    "passed": passed,
    "failed": failed,
    "steps": steps,
}
with open(path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
    f.write("\n")
PY

if [[ "$OUTPUT_FORMAT" == "json" ]]; then
    python3 -c "
import json,sys
r=json.load(open(sys.argv[1], encoding='utf-8'))
r.update({'directory':sys.argv[2],'manifest':sys.argv[1]})
print(json.dumps(r))
" "$output/manifest.json" "$output"
else
    echo
    echo "$passed passed, $failed failed"
    echo "Artifacts: $output"
fi

(( failed == 0 ))
