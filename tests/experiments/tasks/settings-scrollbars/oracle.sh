value="$(defaults read -g AppleShowScrollBars 2>/dev/null || true)"
if [ "$value" = Always ]; then
    printf '{"passed":true,"detail":"AppleShowScrollBars is Always"}\n'
else
    printf '{"passed":false,"detail":"AppleShowScrollBars is %s"}\n' "${value:-unset}"
fi
