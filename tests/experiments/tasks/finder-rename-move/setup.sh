set -eu
rm -rf "$HOME/experiment/inbox" "$HOME/experiment/archive"
mkdir -p "$HOME/experiment/inbox" "$HOME/experiment/archive"
printf 'route comparison draft %s\n' "${MC_EXPERIMENT_SEED:-fixture}" > "$HOME/experiment/inbox/draft.txt"
cp "$HOME/experiment/inbox/draft.txt" "$HOME/experiment/finder-expected.txt"
