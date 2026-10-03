# 061 — Native one-command sudo

Owning topic: [native sudo](../../topics/native-sudo.md).

## Objective and completion conditions

An agent whose sudo would require a TTY password can invoke a bundled helper,
wait for local native authentication, and receive normal command output and
exit status. Show arguments and process ancestry; fail on cancellation,
timeout, invalid requester and unsupported desktop state. Preserve OS policy
without creating a new sudo timestamp. Verify real authentication and an
independent root effect in a claimed dedicated Mac appliance. Commit the
implementation and opt-in YA integration.

## Boundaries

Mac first. No root daemon, product sudoers edits, persisted password,
session-wide arming, remote browser password entry, or replacement of the
resident's typed protected-operation contract. No public release is implied.
Root descendants and same-user shell authority are explicitly disclosed.

## Ordered work

### 1 — implement native authentication

Rust launches fixed system sudo arguments and supplies one-use nonsensitive
context through authenticated local IPC. Swift presents a secure AppKit field
only after code, process-chain, deadline and unlocked-console preflight.

### 2 — bundle native resources

Build ARM64/Intel resources inside Tauri, sign nested executables before the
app, and require the complete pair during package verification. Preserve
verification of release archives predating the feature.

### 3 — advertise an explicit YA capability

Operator opt-in supplies app path and independently trusted publisher. Verify
app and helpers before adding exact-path instructions and environment to local
unrestricted launches. Preserve existing self-session grants. Defaults,
remote execution, plan and sandboxed launches are unchanged.

### 4 — prove real sudo behavior

Unit and launch tests precede signed native fixture testing. Temporary
exact-command PASSWD rules in a claimed dedicated appliance prove password
entry, root UID and root-owned effect. Cancellation, wrong password, timeout,
direct invocation and cache non-creation are refusal cells. Clean up policy,
fixtures, processes, power state and claim.

## Validation and final result

**Current (2026-10-02):** signed helpers from the assembled ARM64 Tauri app
pass dedicated macOS appliance conformance through the common claimed inner
route: direct askpass refusal; existing NOPASSWD behavior; literal argv and
command exit status; native cancellation; wrapper termination with helper
cleanup; concurrent independent prompts; wrong password without another
prompt; visible timeout; real login-password authentication yielding root UID;
and an independently observed root-owned file. A global timestamp policy plus
an independent uncached sudo probe establishes that the invocation creates no
new reusable timestamp. Captured command/driver output contains no password.

Five Rust unit tests, warning-free clippy, ARM64/Intel helper builds, complete
ARM64 Tauri app assembly and nested Developer ID signature verification pass.
YA's 18 touched-area launch/self-session tests, full lint, format and typecheck
pass. Its installed-app probe verifies launch advertisement and rejects wrong
publisher, changed helper bytes and incomplete helper pairs. The default-off
integration adds no client route or protocol fields. Node 25 runs YA checks
without the Node 26/tsx loader deprecation warning; no warning is suppressed.

Temporary password policy, fixture apps, processes and private endpoints are
removed and sudoers validates. The original VM suspension and claim cleanup
are restored after acceptance; its preexisting canonical mode-0600 login
credential was authenticated without changing it.

**Open:** signed/notarized public release, physical-workstation acceptance,
live Intel execution, lock/log-out/headless refusal acceptance, and a
model-driven YA tool turn. The guest has no installed Codex CLI; launch
contract and native authentication were tested separately. No model-session
end-to-end result is claimed. The existing guest unlock helper was absent,
so this task did not add a protected unlock installation for a lock test.
