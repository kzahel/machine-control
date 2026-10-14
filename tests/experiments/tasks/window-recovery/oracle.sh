/opt/homebrew/bin/python3 - <<'PY'
import json
from pathlib import Path
try:
 state=json.loads((Path.home()/'experiment/window-recovery/state.json').read_text())
 passed=state['target']=='Release ready' and state['protected']=='DO NOT EDIT' and state['replacements']==1
 print(json.dumps({'passed':passed,'detail':'replaced target edited and protected window unchanged' if passed else 'wrong target/content/replacement count',
                  'interference':{k:state[k] for k in ('focusChanges','cursorChanges')},'samplingMs':20}))
except (OSError,ValueError,KeyError):
 print(json.dumps({'passed':False,'detail':'fixture state unavailable'}));raise SystemExit(1)
PY
