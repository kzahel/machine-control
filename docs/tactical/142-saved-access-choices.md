# Remember desktop access choices

Owning topic: [host control](../../topics/host-control.md).
Parent: [desktop reliability plan](141-desktop-control-reliability-plan.md).

Status: **complete** for shared preference behavior and the documented Mac
development-bundle restart matrix. The parent owns composed reliability
qualification and release eligibility.

## Objective and completion conditions

Remember selected scopes and duration independently of grants. Settings
recreation, app relaunch, Stop and expiry must not reset choices or silently
arm access. Same-console Mac consent restoration must retain its existing
scope/lifetime checks; logout and boot changes must not inherit authorization.

## Boundaries

Shared UI preferences confer no access. Do not persist owners, pending actions,
credentials or target metadata. Preserve Windows/Linux grant-restoration policy.
The Mac implementation may expose original saved choices to its local operator
without exposing its console binding through the agent API.

## Ordered work

### 1 — persist and validate editable choices

Store the shared form choices in persistent WebView storage. Seed existing Mac
installations from original operator choices, rather than a restricted live
grant or agent-request approval. Report a failed preference write. Keep the
native last-armed choices after Stop without retaining consent authority.

### 2 — verify restart and authority independently

Use an isolated headless browser for the UI regression and native consent
tests for Stop, changed console identity, timed expiry and malformed data.
Extend exact-package VM acceptance with clean quit, crash, fresh task, and
Stop/relaunch checks of both grant state and visible choices. Test reboot as
a distinct boundary; same-console evidence does not establish reboot behavior.

## Validation and current result

The focused UI regression passes recreation, reload, duration/scopes, Stop,
legacy migration, malformed preferences and absence of automatic arming.
Its pinned Playwright/headless-Chromium commands are:

```bash
pnpm --dir desktop install --frozen-lockfile
pnpm --dir desktop exec playwright install chromium --only-shell
pnpm --dir desktop build
pnpm --dir desktop test:access-choices
```

The Mac desktop CI check job runs this regression automatically.
Native consent tests verify remembered choices survive Stop/console replacement
without restoring authority. Bounded signed development-package VM trials
restore all four scopes and indefinite consent after both clean quit and crash.
An additional exact-candidate isolated VM trial verifies the visible four
scope selections and indefinite duration after Stop and clean relaunch, with
approval off. An actual cold boot then preserves those choices while refusing
to restore the previous boot's authorization. Its claim and disposable
workspace were both released. The final development bundle also passes the
200-check sustained campaign and another visible Stop/relaunch/actual-boot
phase, including the separate locked-browser preference. The reboot recording
rerun finishes with zero unpaired commands and complete scope disposal. This
development-bundle evidence is not a release acceptance receipt.

Logout/console replacement and timed-expiry binding have deterministic native
coverage; the live cold-boot cell does not imply a separate live logout pass.
Other platforms retain their existing grant-restoration policies. Remembered
shared form choices do not grant access on any platform.
