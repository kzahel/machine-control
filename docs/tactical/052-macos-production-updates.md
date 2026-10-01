# Mac production updates

Topic: native-distribution
Status: in progress

## Objective

Release 0.3.4 with compact menu-bar Settings and Check for Updates commands,
deploy the existing update endpoint, and prove an installed signed 0.3.3 app
updates through that production route.

## Completion conditions

- Production route returns the shared server's platform-specific signed
  metadata, and 204 for current clients.
- Both Mac packages pass signed CI verification; ARM64 Tart passes native
  operator, tray navigation, Stop, and Quit acceptance before publication.
- Tagged CI publishes the complete immutable 0.3.4 release with required notes.
- Public 0.3.3 discovers, installs, and relaunches public 0.3.4 in Tart;
  permissions remain ready, access stays off, and resident generation changes.
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

Tagged publication and installed public-update acceptance remain pending.
