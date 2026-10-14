root="$HOME/experiment/window-recovery"
for name in launch.log state.json pid; do
    printf '\n%s\n' "$name"
    cat "$root/$name" 2>/dev/null || true
done
if [ -f "$root/pid" ]; then
    ps -p "$(cat "$root/pid")" -o pid,stat,comm || true
fi
