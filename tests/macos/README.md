# macOS conformance

The macOS corpus drives the target-resident facade provided by the sibling
`macvm-testbed` repository. `conformance.sh` runs the same request vocabulary
through two placements:

- `remote`: the host wrapper sends a request through `tart exec`; and
- `local`: `tart exec` launches the installed guest-local client, which calls
  the same private resident socket.

The deterministic AppKit fixture supplies both visible AX state and a separate
file oracle. Tests do not treat an AX or input acknowledgement as proof of an
application effect. The script also checks exact-window artifacts, resident
restart, stale-reference refusal, and System Settings background behavior.
`aqua-visual-fallback.sh` runs with Tart-window pixels and input forbidden. It
checks target-local full-display capture at Retina scale and move, click, drag,
and scroll on a deliberately sparse custom AppKit surface. Its file oracle
proves guest effects, while an independent read-only host oracle proves the
host cursor and frontmost application did not change. Both outside and
guest-local callers exercise the same resident.
`privacy-consent.sh` uses a signed fixture and file oracle to reset and replay
Camera, Microphone, and Automation prompts. Each class proves both Don't Allow
and Allow through native system-dialog semantics, distinguishes policy from
Tart's missing camera/microphone hardware, and alternates outside and
guest-local calls without host interference.
`privacy-settings.sh` covers settings-managed Accessibility, Input Monitoring,
and Screen Recording grants and revocation. It drives the Privacy & Security
pane, proves a real event tap and ScreenCaptureKit enumeration after the
relevant grants, and uses the resident's bounded one-shot credential lease only
when macOS presents the strict inline administrator window. The credential
cases are interactive and never put the secret in request JSON, arguments,
environment, files, logs, captures, or results.
`real-applications.sh` sustains the same facade across Finder, System Settings,
TextEdit, Safari, an application menu bar, exact-window artifacts, focus
preservation, and owned-state cleanup.
`provider-comparison.sh` runs identical compact snapshot, action, independent
fixture-effect, and exact-window capture cells through native macOS and Cua
routes. It then proves native Dock and Control Center reach while requiring
any Cua gap to fail closed without fallback.
`administrator-sheet.sh` proves that a normal Aqua administrator sheet can be
identified, cancelled, and submitted entirely inside the guest. It exercises
wrong-requester, cancellation, expiry, changed-sheet, resident-restart,
incorrect-credential, correct-credential, reboot-recovery, and cleanup cases.
The two credential cases are interactive by design: the secret is read without
echo by the testbed's one-shot helper and never enters request JSON or this
repository.

Run it from this repository after selecting a guarded disposable/candidate VM
in the testbed's ignored local configuration:

```bash
tests/macos/conformance.sh
tests/macos/conformance.sh remote
tests/macos/conformance.sh local
tests/macos/aqua-visual-fallback.sh
tests/macos/privacy-consent.sh
tests/macos/privacy-settings.sh
tests/macos/real-applications.sh
tests/macos/provider-comparison.sh
tests/macos/administrator-sheet.sh
tests/macos/administrator-sheet.sh session
```

No target name, guest account, network endpoint, or captured artifact is
written into this repository.
