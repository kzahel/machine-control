# Native signing smoke

Status: active.

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

Implementation is ready for hosted execution. Local workflow lint and shell
syntax checks pass, all seven real-signature rejection tests pass, and the
macOS ARM64 fixture builds, executes with the expected source identity, and
packages successfully. Signing and notarization acceptance are pending.
