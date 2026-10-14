set -eu
mkdir -p "$HOME/experiment/probe-ext"
printf '%s\n' '{"manifest_version":3,"name":"Route Probe","version":"1.0.0"}' \
    > "$HOME/experiment/probe-ext/manifest.json"
. "$HOME/experiment/common-chrome.sh"
start_chrome about:blank
