set -eu
defaults write -g AppleShowScrollBars Automatic
test "$(defaults read -g AppleShowScrollBars)" = Automatic
