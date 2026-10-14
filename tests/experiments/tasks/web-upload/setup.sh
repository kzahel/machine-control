set -eu
mkdir -p "$HOME/experiment"
printf '%s\n' 'upload me' > "$HOME/experiment/upload-me.txt"
cat > "$HOME/experiment/upload.html" <<'HTML'
<!doctype html><title>waiting</title>
<h1>Upload a file</h1><input type="file" id="file" aria-label="Choose file">
<script>file.onchange=()=>{document.title='selected:'+(file.files[0]||{}).name}</script>
HTML
. "$HOME/experiment/common-chrome.sh"
start_chrome --remote-debugging-port=9223 "file://$HOME/experiment/upload.html"
