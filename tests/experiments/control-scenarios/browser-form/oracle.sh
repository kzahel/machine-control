set -eu
root="$HOME/experiment/heldout-browser"
kill -0 "$(cat "$root/server.pid")" 2>/dev/null
/opt/homebrew/bin/python3 "$HOME/code/machine-control/tests/experiments/control-scenarios/browser-form/fixture.py" oracle --root "$root"
