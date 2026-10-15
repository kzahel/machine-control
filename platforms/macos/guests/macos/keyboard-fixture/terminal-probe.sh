#!/bin/bash
# Runs in a real Terminal PTY. Readline edits are proved by NUL-delimited lines,
# never by executing the typed text as shell commands.
set -euo pipefail
root="$1"
printf '\033]0;Machine Control Keyboard Terminal\007'
printf 'Machine Control keyboard terminal oracle\n'
printf 'ready\n' > "$root/terminal-ready"
while IFS= read -e -r -p 'Keyboard probe> ' line; do
    printf '%s\0' "$line" >> "$root/terminal-lines"
done
