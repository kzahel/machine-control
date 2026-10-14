set -eu
mkdir -p "$HOME/experiment"
/opt/homebrew/bin/python3 - <<'PY'
from pathlib import Path
import random,os
(Path.home()/'experiment/upload-me.txt').write_text('Upload fixture '+random.Random(os.environ.get('MC_EXPERIMENT_SEED','qualification')).randbytes(24).hex()+'\n')
PY
cat > "$HOME/experiment/upload.html" <<'HTML'
<!doctype html><title>waiting</title>
<h1>Upload a file</h1><input type="file" id="file" aria-label="Choose file">
<script>
file.onchange=async()=>{
 const selected=file.files[0];
 if(!selected){document.title='waiting';return;}
 const hash=await crypto.subtle.digest('SHA-256',await selected.arrayBuffer());
 const hex=Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');
 document.title='uploaded:'+selected.name+':'+hex;
};
</script>
HTML
. "$HOME/experiment/common-chrome.sh"
start_chrome --remote-debugging-port=9223 "file://$HOME/experiment/upload.html"
