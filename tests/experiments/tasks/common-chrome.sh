# Sourced by task setup scripts: start a disposable Chrome for Testing profile.
# --force-renderer-accessibility exposes web content to both routes alike.
chrome_app="$HOME/mc-cft/chrome-mac-arm64/Google Chrome for Testing.app"
start_chrome() {
    rm -rf "$HOME/experiment/cft-profile"
    open -na "$chrome_app" --args --user-data-dir="$HOME/experiment/cft-profile" \
        --no-first-run --no-default-browser-check --use-mock-keychain \
        --password-store=basic --force-renderer-accessibility "$@"
    sleep 6
}
