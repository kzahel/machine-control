set -eu
root="$HOME/experiment/window-recovery"
app="$root/Window Recovery.app"
mkdir -p "$app/Contents/MacOS"
/usr/bin/swiftc "$HOME/code/machine-control/tests/experiments/tasks/window-recovery/Fixture.swift" -o "$app/Contents/MacOS/Fixture" -framework AppKit
cat > "$app/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>Fixture</string>
<key>CFBundleIdentifier</key><string>dev.machinecontrol.experiment.windowrecovery</string>
<key>CFBundleName</key><string>Window Recovery</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSUIElement</key><false/>
</dict></plist>
/usr/bin/codesign --force --sign - "$app" >/dev/null 2>&1
nohup "$app/Contents/MacOS/Fixture" "$root" > "$root/launch.log" 2>&1 &
printf '%s\n' "$!" > "$root/pid"
for _ in 1 2 3 4 5; do
    [ -f "$root/state.json" ] && exit 0
    sleep 1
done
exit 1
