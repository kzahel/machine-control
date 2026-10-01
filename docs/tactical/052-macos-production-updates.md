# Mac production updates

Topic: native-distribution
Status: complete; 0.3.5 published and ARM64 production updates accepted

## Objective

Release compact menu-bar Settings and Check for Updates commands, deploy the
existing update endpoint, and prove installed signed updates through that route.
Preserve the published 0.3.4 release and ship its relaunch repair as 0.3.5.

## Completion conditions

- Production route returns the shared server's platform-specific signed
  metadata, and 204 for current clients.
- Both Mac packages pass signed CI verification; ARM64 Tart passes native
  operator, tray navigation, Stop, and Quit acceptance before publication.
- Tagged CI publishes the complete immutable 0.3.4 release with required notes.
- A signed repair fixture automatically updates to public 0.3.4 in Tart;
  permissions remain ready, access stays off, and resident generation changes.
- Tagged CI publishes immutable 0.3.5 with the required legacy-reopen note.
- Public 0.3.3 updates to public 0.3.5 with any required reopening reported;
  signed 0.3.5 passes Permissions Restart, operator, tray, Stop and Quit.
- Original testbed application, policy, power state, and claim are restored.

## Boundaries

The shared update server owns release selection and Tauri metadata. The website
proxies the stable product endpoint without duplicating that protocol. Public
product configuration belongs here; concrete deployment belongs in private
infrastructure. No automatic installation, permission bypass, new providers,
or Windows/Linux desktop packaging is included. Intel package authenticity is
required; Intel execution and physical-host acceptance remain separate.

## Ordered work

### 1 — expose update checks and tray navigation

Register the desktop release family on the shared server, proxy only supported
Mac update paths, and expose compact Settings and Check for Updates menu items.
Keep native update lifecycle enforcement and explicit installation.

### 2 — accept the signed candidate

Run source, proxy, release, and native checks. Build both signed architectures
in CI. Authenticate exact packages, then exercise ARM64 in claimed Tart using
the resident observer and an independent fixture.

### 3 — publish and exercise the production update

Create the annotated version tag through the release script. Require successful
automatic draft verification/publication. Re-download public packages and
verify the feed and website. Install public 0.3.3, check and install through its
visible UI, and verify 0.3.4 relaunch and retained permissions. Restore the VM.

## Validation and result

Production routing is deployed: the corrected website workflow passed, both
Mac architectures return signed metadata for older clients and 204 for current
clients, and the Tart guest can reach the endpoint. Six website tests, desktop
build/Clippy, 44 native resident tests, 37 release tests, native static checks,
and portable checks passed. Both signed candidate architectures passed
[CI](https://github.com/kzahel/machine-control/actions/runs/36825993636) and
local re-download authentication, including tamper rejection.

Native operator acceptance passed under a verified caller-owned claim.
The first acquisition was refused but its diagnostic active claim was
incorrectly extracted; another task suspended the guest during testing. The
caller-owned claim was subsequently acquired and verified, and the original
application, policy and LaunchAgent were restored before repeating acceptance.
The public claim example now requires JSON acceptance before extracting an ID.

The tray harness also now uses native pointer input at freshly observed
status-item bounds: AXPress acknowledged delivery without opening the menu.
Menu visibility and resulting application state establish effect. WebKit
status text is read from its AX value rather than assuming an AX label.

The signed ARM64 candidate passed a 0.3.3 package upgrade with permissions
retained, grants revoked, generation change and stale-reference refusal.
Visible denial, narrowed approval, independent fixture effect, self/protected
refusal, approval-prompt input pause, global Stop, and tray Settings, manual
production check, Open and Stop passed. Real tray Quit exited with status zero without respawn. Original app, policy,
LaunchAgent, and readiness were restored, and owned staging was removed.

The annotated `desktop-v0.3.4` tag points to
`8d076efd1d18fa9a97faf0d90d2f12479260c29c`. The first
[tagged workflow](https://github.com/kzahel/machine-control/actions/runs/36830572285)
attempt stopped on Apple notarization HTTP 403 for a missing or expired
agreement. After the Account Holder accepted it, read-only access cleared
and all jobs were rerun without moving the tag. Attempt 2 succeeded and
published the complete nine-asset release with the exact required changelog.
Both re-downloaded public package families passed signatures, notarization,
stapling, updater signature/version, receipt identity and tamper rejection.
Both website download routes select the exact 0.3.4 DMGs. Both architectures
on the shared server and website proxy offer signed 0.3.4 metadata to 0.3.3
and return 204 to 0.3.4.

**Current:** The claimed ARM64 production test installed public 0.3.3 from
its DMG, discovered 0.3.4 through Settings, refused installation with active
access, and replaced the bundle with public 0.3.4 after Stop. Automatic
relaunch did not return a resident: the LaunchAgent reported a clean exit
without a running PID. That run did not establish installed production-update acceptance. The original app, policy, LaunchAgent and suspended state
were restored, owned guest staging was removed, and the claim was released.

**Current:** The event-loop-only repair was built as a signed 0.3.3 fixture
from `35a77bee7ec2d49c9e715bce9fad64d0451ad8d7` in
[CI](https://github.com/kzahel/machine-control/actions/runs/36839781314).
Both architecture packages passed independent authentication and tamper checks,
but the installed fixture still failed automatic relaunch after updating to
public 0.3.4. Application, policy, LaunchAgent, power and claim were restored.

**Current:** A native launchd diagnostic observed an ordinary child's delayed
file effect disappear when its parent exited; explicit process-group/session
children completed. The diagnostic's assumption about the ordinary child's
reported group was false, so only the independently observed effects are
accepted evidence. A separate regression test reproduced inheritance of the
resident's live Unix listener by a plain spawned child. The close-on-exec repair
passes that test and all 45 resident tests. Local ad-hoc application attempts
failed readiness before testing the proposed handoff; they do not establish
signed lifecycle or permission acceptance.

**Decision:** Use a bounded Mac restart helper in its own process group. Wait
for the old process to exit, preserving normal Tauri Exit cleanup, then execute
the installed binary with its original arguments. Mark native sockets
close-on-exec. Permissions Restart revokes access through the same native
handoff. Installer maintenance stops the live resident, including a detached
replacement, and relies on RunAtLoad rather than a second forced startup.
Prove this correction with a signed older-version fixture updating through the
actual public feed before publishing the next patch. Older published senders
cannot be changed: their first update may require reopening the installed app.
Keep that limitation explicit. Do not move the 0.3.4 tag or replace its bytes.

**Current:** The bounded restart repair from
`4661d79d37ffda8abac83e5dc6a2c425faf9fbb9` passed both signed architecture
builds in [CI](https://github.com/kzahel/machine-control/actions/runs/36849762988)
and independent package authentication/tamper checks. In claimed ARM64 Tart,
the signed 0.3.3-version fixture passed Permissions Restart with access revoked,
then automatically installed and launched public 0.3.4 through the real feed.
Permissions remained ready, generation changed, access stayed off, and stale
references were refused. Visible denial, narrowed approval, independent fixture
effect, self/protected refusal, prompt pausing, global Stop, tray Settings/check/
Open/Stop, and real Quit without a surviving app PID or respawn passed. Original
application, policy, LaunchAgent, readiness and suspended power were restored;
owned guest staging was removed and the verified caller-owned claim released.
The annotated `desktop-v0.3.5` tag points to
`2b91b005b4991e33ef86121d395df215946c7d94`.
[Tagged CI](https://github.com/kzahel/machine-control/actions/runs/36852715035)
passed and published all nine assets with the exact required changelog. Both
re-downloaded public package families passed publisher signatures,
notarization/stapling, updater signature/version, source/run receipts, GitHub
asset hashes/sizes and tamper rejection. Both website download routes select
the exact 0.3.5 DMGs. Both architectures on the shared server and website proxy
offer the exact signed archive to 0.3.3/0.3.4 and return 204 to 0.3.5.
Feed verification initially assumed only the newest notes; source review
confirmed the existing cumulative-notes contract. Skipping 0.3.4 returns both
required changelogs; a 0.3.4 client gets only 0.3.5's notes.

**Final result:** Public 0.3.3 discovered and installed public 0.3.5 through
Settings, with installation disabled while access was active. One native reopen
was needed for the immutable old sender's relaunch defect and is reported
separately from automatic acceptance. Permissions remained ready, access stayed
off, generation changed, and stale references were refused. The released 0.3.5
Permissions Restart then relaunched automatically and revoked access.
Visible denial, narrowed approval, independent fixture effect, self/protected
refusal, approval-prompt input pause, global Stop, tray Settings/check/Open/Stop,
and real Quit without a surviving PID or respawn all passed. Original app,
policy, LaunchAgent, readiness and suspended power were restored, owned staging
was removed, and the exclusive caller-owned claim was released. The canonical
controller-local appliance credential handoff remains ready and mode 0600.

The repair fixture establishes automatic production-feed handoff from the fixed
sender code; the public-client run establishes legacy installation/reopening
and released 0.3.5 Restart/operator behavior. Physical Mac and Intel execution
remain open. No host UI or TCC bypass was used.
