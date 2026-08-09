# Windows conformance

The Windows suites exercise the same installed facade from two placements:

- `conformance.ps1` drives ordinary system-shell and window behavior through
  an authenticated administration carrier.
- `provider-composition.ps1` runs the deterministic fixture workflow through
  Cua and native providers from either remote or local placement. Its optional
  failure lane terminates only the supervised Cua child to prove bounded
  restart, stale-reference, timeout, and disclosed fallback behavior.
- `provider-absence.ps1` is an explicitly confirmed, reversible package test.
  It withholds the installed Cua executable after revocation, proves truthful
  unavailable capability and native observation fallback, then restores the
  exact file and revokes the temporary helper generation.
- `run-local-probe.cmd` starts `local-probe.ps1` as the logged-in Medium user
  and proves that it reaches the same named pipe and result contract.
- `uac-conformance.ps1` originates elevation from the Medium fixture, cancels
  and approves genuine secure-desktop prompts, and verifies a High-integrity
  fixture through an independent marker.
- `lifecycle-conformance.ps1` runs separately authorized lock, logout, or
  protected-state inspection and records only minimized route/state evidence.
- `scripts/login-windows.sh` is the separately supervised PIN/password
  acceptance route. It prompts the human without echo and uses the runtime's
  dedicated non-JSON secret channel.

`scripts/bootstrap-windows.sh` is the reproducible host-to-target installation
path used before these suites. It detects ARM64/x64, builds and verifies the
matching package, installs through administrative SSH, waits for the Medium
helper and adopted providers, and removes transfer staging. It assumes a
testbed-ready Windows base; it is not an OOBE or credential bootstrap.

The suites write generated evidence only to caller-selected target-local paths.
Do not commit raw output or screenshots. A testbed operator must separately
authorize and supervise lock, logout, reboot, and credential-gated recovery.

Before running UAC conformance, verify all three policy conditions:

- UAC is enabled;
- administrator elevation requires consent; and
- consent prompts use the secure desktop.

The test is invalid if policy is weakened to avoid `Winlogon`. When semantic
controls are unavailable, the result must identify target-local pixels/input
as a fallback rather than count delivery as a semantic pass.

Credential login is intentionally not an unattended suite. Begin from a real
no-user `Winlogon` state, run the helper once with `pin` or `password`, and
independently confirm WTS user state, the `Default` input desktop, and a fresh
Medium helper. Never put the credential in a PowerShell command, test
parameter, JSON fixture, environment variable, evidence file, or deliberate
wrong-credential case. A discovery refusal must end the case without retrying.

`provider-composition.ps1 -Placement local` deliberately skips
`service.revoke`: a local caller is a child of the helper generation, and
successful revocation is expected to terminate that process tree. The remote
lane proves revocation and helper recreation instead.
