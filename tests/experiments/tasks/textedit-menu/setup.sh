set -eu
mkdir -p "$HOME/experiment/out"
rm -f "$HOME/experiment/out/menu-note.txt"
printf '%s' '{\rtf1\ansi\b Menu conversion fixture\b0}' > "$HOME/experiment/menu-source.rtf"
open -a TextEdit "$HOME/experiment/menu-source.rtf"
