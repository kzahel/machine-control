root="$HOME/experiment"
if [ -f "$root/archive/final.txt" ] && [ ! -e "$root/inbox/draft.txt" ] && [ ! -e "$root/inbox/final.txt" ] &&
   grep -q 'route comparison draft' "$root/archive/final.txt"; then
    printf '{"passed":true,"detail":"archive/final.txt holds the original contents"}\n'
else
    printf '{"passed":false,"detail":"expected only archive/final.txt with the original contents"}\n'
fi
