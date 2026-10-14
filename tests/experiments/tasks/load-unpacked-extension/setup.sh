set -eu
mkdir -p "$HOME/experiment/probe-ext" "$HOME/experiment/extension-page"
/opt/homebrew/bin/python3 - <<'PY'
import json,random,os
from pathlib import Path
root=Path.home()/'experiment'
nonce=random.Random(os.environ.get('MC_EXPERIMENT_SEED','qualification')).randbytes(12).hex()
(root/'extension-expected.txt').write_text('extension:'+nonce)
(root/'probe-ext/manifest.json').write_text(json.dumps({
 'manifest_version':3,'name':'Route Probe','version':'1.0.0',
 'content_scripts':[{'matches':['http://127.0.0.1:9225/*'],
                     'js':['probe.js'],'run_at':'document_idle'}]}))
(root/'probe-ext/probe.js').write_text('document.title='+json.dumps('extension:'+nonce)+';')
(root/'extension-page/index.html').write_text('<!doctype html><title>extension inactive</title><h1>Extension probe</h1>')
PY
nohup /opt/homebrew/bin/python3 -m http.server 9225 --bind 127.0.0.1 \
    --directory "$HOME/experiment/extension-page" > "$HOME/experiment/extension-server.log" 2>&1 &
. "$HOME/experiment/common-chrome.sh"
start_chrome --remote-debugging-port=9223 about:blank
