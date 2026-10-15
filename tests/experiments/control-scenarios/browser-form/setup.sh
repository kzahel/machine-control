set -eu
fixture="$HOME/code/machine-control/tests/experiments/control-scenarios/browser-form/fixture.py"
root="$HOME/experiment/heldout-browser"
/opt/homebrew/bin/python3 "$fixture" setup --root "$root" --seed "${MC_EXPERIMENT_SEED:?}"
/opt/homebrew/bin/python3 "$fixture" serve --root "$root" --port 0 > "$root/server.log" 2>&1 &
printf '%s\n' "$!" > "$root/server.pid"
for attempt in $(seq 1 100); do
  [ ! -f "$root/server.json" ] || break
  kill -0 "$(cat "$root/server.pid")" 2>/dev/null || exit 1
  sleep .1
done
url=$(/opt/homebrew/bin/python3 - "$root" <<'PY'
import json,sys,urllib.request
from pathlib import Path
root=Path(sys.argv[1])
url=json.loads((root/'server.json').read_text())['url']
with urllib.request.urlopen(url,timeout=5) as response:
    assert response.status==200
print(url)
PY
)
. "$HOME/experiment/common-chrome.sh"
start_chrome "$url"
