# Native signing smoke

Status: complete.

Owning topic: [native-distribution](../../topics/native-distribution.md).

## Objective and completion conditions

Establish Actions signing infrastructure with existing publisher credentials
and an independent package key. Complete when a manual main-branch run builds
and executes Windows/macOS/Linux fixtures, verifies Windows Authenticode,
notarizes/staples/verifies a Mac bundle with a nested helper, and uploads a
complete manifest-signed artifact set that independently verifies.

## Boundaries

No desktop control, resident installation, Tauri app, consumer integration,
provider redistribution, VM/device use, or public release publication.
Credentials and concrete deployment values stay private. Only the package
verification public key is checked in.

## Ordered work

### 1 — establish release authority

Create a main-only release environment; provision existing Apple/Azure
credentials, private publisher variables, and a dedicated minisign key. Keep
private backup and its locator outside this repository.

### 2 — build and verify signed native fixtures

Build inert executables on matching runners, binding output to source SHA.
Sign Windows code and verify publisher/timestamp. Sign the Mac helper/bundle
inside-out, notarize, staple, and assess Gatekeeper.

### 3 — authenticate the complete artifact set

Require all platforms, package final signed bytes, sign a source/run-bound
manifest, and verify with the pinned public key before uploading. Keep public
release publication unavailable in this workflow.

## Validation

Run actionlint, shell syntax, native execution, and real minisign rejection
tests. Validate the hosted workflow and independently download/verify its
artifact. Source tests alone do not prove signing or notarization.

## Result

Accepted on 2026-09-12. The
[complete signing run](https://github.com/kzahel/machine-control/actions/runs/34679710890)
passed all four jobs for source
`edf0bd4a5d3259dd3ffcb539798f46627dfe0b91`:

- Windows x64 built and executed natively, received an Authenticode signature,
  and passed publisher, timestamp, and signed-execution checks.
- macOS ARM64 built its application and nested helper, signed both with
  Developer ID and hardened runtime, received accepted notarization, and
  passed stapling, Gatekeeper, strict signatures, and signed execution.
- Linux x64 built, executed, and packaged its fixture.
- Finalization passed seven real-signature rejection tests and authenticated
  the complete three-package manifest with the pinned public key.

The downloaded `verified-signing-smoke` artifact independently passed manifest
signature, exact source/run identity, and all three package hash/length checks.
The extracted Mac bundle passed strict signature verification, stapler
validation, and Gatekeeper on a separate Mac. Both downloaded executables ran
and returned the expected source identity. All six
[ordinary CI jobs](https://github.com/kzahel/machine-control/actions/runs/34679702594)
also passed for that source. Local workflow lint, shell syntax, and portable
checks passed during implementation.

The initial run proved missing-credential refusal. Subsequent hosted execution
exposed two integration fixes: select the temporary keychain in the runner's
search list/default and restore both during cleanup; prefix an inline
codesign requirement with `=`. Neither required new publisher credentials.

No public release or resident installation was performed. Runtime packaging,
workstation permissions, installed upgrades, and additional architectures
remain in the owning distribution topic.
