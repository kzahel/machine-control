prefs="$HOME/experiment/cft-profile/Default/Secure Preferences"
for _ in 1 2 3 4 5; do grep -q 'experiment/probe-ext' "$prefs" 2>/dev/null && break; sleep 2; done
if grep -q 'experiment/probe-ext' "$prefs" 2>/dev/null; then
    printf '{"passed":true,"detail":"profile records the probe extension path"}\n'
else
    printf '{"passed":false,"detail":"probe extension path absent from the profile"}\n'
fi
