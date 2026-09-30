import json
from pathlib import Path
import re
import sys
version = sys.argv[1]
if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
    raise SystemExit('Candidate version must be numeric x.y.z')
root=Path(__file__).resolve().parents[1]
for file in (root/'package.json', root/'src-tauri/tauri.conf.json'):
    value=json.loads(file.read_text());value['version']=version;file.write_text(json.dumps(value,indent=2)+'\n')
file=root/'src-tauri/Cargo.toml'
file.write_text(re.sub(r'^version = "[^"]+"',f'version = "{version}"',file.read_text(),count=1,flags=re.M))
