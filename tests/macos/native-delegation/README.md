# Signed native delegation acceptance

This opt-in runner exercises the actual signed YA native shell, credentialed
server session, local provider adapter, installed MC CLI and signed MC operator
app. It uses an owned Codex app-server protocol fixture; no model, sub-agent or
real provider login runs. An independent AppKit counter proves two native AX
effects. Native AX operates the candidate's trust checkbox, Pause, Resume and
Stop through a separate standing-policy appliance resident. No trust setter or
positive admission hook is injected into the candidate.

Use only an exclusively claimed, disposable Mac appliance with a healthy
native resident, passwordless appliance administration and the installed MC
AppKit fixture. Both supplied apps must be sealed signed candidates. The
runner temporarily selects workstation policy and replaces canonical YA on
that guest; it restores policy, consent/trust files, the previous application
and the original resident socket in cleanup. It reaps only owned processes.
Never use a personal workstation. The caller owns doctor/claims/power cleanup.
No primary browser, TCC database or protected helper is touched.

Build YA's server with its supported runtime, then prepare a fresh private
fixture profile using its real AuthService:

```sh
fixture_dir="$(mktemp -d)"
node tests/macos/native-delegation/prepare-auth.mjs \
  /path/to/yepanywhere/packages/server/dist/auth/AuthService.js "$fixture_dir"
python3 tests/macos/native-delegation/run.py \
  --target macos --claim CLAIM \
  --mc-app '/path/to/Machine Control.app' \
  --ya-app '/path/to/YepAnywhere.app' \
  --auth-data "$fixture_dir/data" \
  --auth-session-file "$fixture_dir/auth.private.json"
```

All concrete paths, claims, cookies and diagnostic logs stay private. The
cookie fixture must be mode 0600. Default cleanup removes the guest's isolated
directory after independently checking restoration. `--keep-artifacts` retains
private diagnostics for explicit caller cleanup; failed restoration retains
recovery material automatically. Each wait/operation is bounded. Provider
requests are never retried after an uncertain effect.

Cases: native operator enrollment; credentialed live launch; independent AX
counter delta; unrelated same-user CLI refusal even with the public locator;
Pause keeps trust and fences old work; Resume waits through a fresh notice and
accepts fresh ownership; Stop refuses current work and fresh reconnect, including
after signed resident restart. This
bounded run does not qualify protected/covered use, genuine hardware takeover,
all signed negatives, restart failures or release distribution. Tactical 086
owns evidence and remaining gates.
