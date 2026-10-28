# Security

## Supported deployment profile

The current implementation is an experimental
`dedicated-test-appliance` profile. Its LocalSystem service can place a helper
on the active or secure Windows desktop and perform typed UI Automation,
capture, keyboard, pointer, lock, logout, and stock Credential Provider login
operations. That authority is intentional for an isolated and rebuildable test
target.

Do not leave this profile installed on a personal or shared workstation. The
local named pipe permits authenticated local Windows users, so it is an
ergonomic authorization boundary for a dedicated appliance, not hostile-user
containment. A shell running as an admitted user can call every armed
operation. SSH and tunnels carry calls but do not replace endpoint
authentication or authorization.

The protected API deliberately omits arbitrary command execution, filesystem,
registry, service-management, credential storage, and policy-widening
operations. It does include a typed, one-submission stock Credential Provider
login route for dedicated test appliances. Other administration belongs to a
separately authorized transport.

## Ordinary provider subprocess

The installed runtime supervises the unmodified Cua 0.17.0 release only as a
child of the Medium interactive helper. It uses a private generation-scoped
named pipe, disables upstream telemetry and update checks, and never starts Cua
inside the LocalSystem protected worker. Package manifests verify the exact
evaluated executable digest and include the upstream MIT license.

The upstream release artifact does not attest the source commit that produced
it; the separately recorded source-review SHA is not a binary-provenance
claim. Treat this as an explicit supply-chain limitation until a reproducible
or attested build replaces the evaluated binary. Provider crashes invalidate
facade references and permit one supervised restart, not unbounded replay of
mutating actions.

## Credential route

PIN/password login is absent from the ordinary JSON request surface. The local
CLI accepts only credential kind as an argument and reads the secret from
redirected standard input; `scripts/login-windows.sh` prompts without echo. A
dedicated binary pipe carries the secret to the service, and a randomly named
SYSTEM-only one-shot pipe carries it to a disposable Winlogon worker.

The worker must positively discover the requested stock provider and edit
field before it reads the secret. It submits once, never retries an unknown or
failed result, takes no screenshot during entry, returns only redacted state,
and clears mutable byte/character buffers on a best-effort basis. Credential
material still exists briefly in caller, SSH, service, and worker process
memory; this design does not claim protection against an administrator or a
hostile admitted local user.

## Evidence and secrets

Screenshots and detailed results stay on the target and can contain private
information. Do not commit them. Public evidence must omit machine and account
names, addresses, device identifiers, process and window identifiers, private
paths, screenshot hashes, and captured content.

The repository must never contain passwords, PINs, SSH material, RustDesk IDs,
tokens, certificates, private endpoints, credential values, or private target
inventory. Login requires an explicitly authorized human or future secret
provider outside the ordinary agent-visible request path.

## Dependency maintenance

Dependabot proposes grouped security updates and weekly maintenance updates
for the active npm, Cargo, and GitHub Actions manifests. The iOS native runner
stays pinned; its HTTP client is updated through a scoped pnpm override.
The retired ChromeOS MCP project has been removed. Current ChromeOS bootstrap
and control use the separate dependency-free Python helpers.

`Security checks` audits frozen npm graphs, the desktop and Mac helper Cargo
locks, and the optimized GLib backport regression. Tauri's GTK3 dependency
still requires GLib 0.18; the local
[compatibility backport](desktop/vendor/glib/MACHINE-CONTROL.md) applies the
upstream fix for GHSA-wrw7-89jp-8q8g. Its original version is retained rather
than relabeled as a fixed upstream release. A path dependency is not covered
by registry version matching, so the dedicated regression is required.

CodeQL scans Actions, JavaScript/TypeScript, Python, C#, C/C++, and Rust without
a product build. This is static coverage, not packaged or live-target
acceptance; generated code, Swift, and Objective-C are not covered by this
workflow. Rust audit reports unmaintained dependencies for review and fails
on known vulnerabilities and unsoundness.

The remaining maintenance warnings are `proc-macro-error` through GTK3 and
the `zvariant`, `zvariant_derive`, and `zbus_names` packages through the Linux
single-instance plugin. The latter require an upstream migration to zbus 6;
they cannot be replaced by a compatible lockfile update. These informational
warnings remain visible rather than being suppressed or treated as fixed.
The vendored upstream test graph also uses unmaintained `basic-toml`; that
dependency is not part of the shipped desktop application.

CodeQL triage keeps the queries enabled. Doctor output includes credential-kind
labels, wipe-policy counts, and passcode-required booleans. Experiment receipts
include a private credential-file locator and equality/permission verification
booleans; credential bytes are written only to the separate mode-0600 secret
store. Those metadata flows are reviewed false positives for clear-text secret
logging/storage. The browser indicator restores a favicon `link` element's
original `href` in the page DOM; this image-resource context does not execute
an HTML document or a JavaScript URL. That restoration is a reviewed false
positive for DOM XSS. New findings still require individual review.

## Reporting

This prototype has no published security-response address yet. Until one
exists, avoid filing public issues containing secrets or deployment details;
report only minimized, reproducible implementation defects.
