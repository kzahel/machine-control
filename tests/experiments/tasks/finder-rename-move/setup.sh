set -eu
rm -rf "$HOME/experiment/inbox" "$HOME/experiment/archive"
mkdir -p "$HOME/experiment/inbox" "$HOME/experiment/archive"
printf '%s\n' 'route comparison draft' > "$HOME/experiment/inbox/draft.txt"
