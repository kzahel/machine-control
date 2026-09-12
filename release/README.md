# Native signing smoke

The real Windows workstation preview is implemented separately in
[windows-workstation.md](windows-workstation.md) and
[Tactical 036](../docs/tactical/036-windows-workstation-distribution.md).
Its manual [workflow](../.github/workflows/windows-workstation.yml) builds
ARM64/x64 self-contained residents, signs the provider before binding its final
digest into the host, signs the host/lifecycle script and full file catalog,
then authenticates the final archives with a dedicated preview manifest.
It produces temporary CI artifacts, not a public release or automatic update
feed. Native interactive acceptance remains a separate gate.

```bash
gh workflow run windows-workstation.yml --ref main
gh run download RUN_ID --name verified-windows-workstation --dir artifacts/workstation-download
python3 release/workstation-manifest.py verify artifacts/workstation-download \
  --revision FULL_SOURCE_SHA --run RUN_ID.ATTEMPT
```

For an unsigned local development payload, run `release/windows-package.py
build OUTPUT --runtime win-arm64 --revision FULL_SOURCE_SHA`, then its
`archive OUTPUT --output ARCHIVE_DIRECTORY` command. Select `win-x64` for the
other architecture. Local modified builds disclose `sourceDirty` in build.json.
The package carries the pinned Cua license/provenance and the exact restored
.NET dependency licenses/notices; this does not establish new upstream binary
source provenance.

This directory owns the first release-engineering proof for an optional
Machine Control component. The native fixture prints its platform and exact
source revision, then exits. It has no control API, service registration,
permission requests, or UI. It packages no resident or third-party provider.
See [native distribution](../topics/native-distribution.md) and
[Tactical 035](../docs/tactical/035-native-signing-smoke.md).

**Current:** The [complete hosted smoke run](https://github.com/kzahel/machine-control/actions/runs/34679710890)
passed Windows signing, Mac signing/notarization, Linux packaging, and manifest
verification. Its downloaded artifact was independently verified. Tactical 035
records the exact source and evidence boundaries.

## Run and retrieve

The manual [workflow](../.github/workflows/signing-smoke.yml) only runs from
`main`. Its repository permission is read-only. It never publishes a GitHub
Release, pushes a tag, or deploys a resident.

```bash
gh workflow run signing-smoke.yml --ref main
gh run list --workflow signing-smoke.yml --limit 5
gh run download RUN_ID --name verified-signing-smoke --dir artifacts/downloaded-smoke
python3 release/manifest.py verify artifacts/downloaded-smoke \
  --revision FULL_SOURCE_SHA --run RUN_ID.ATTEMPT
```

Verification requires `minisign` and uses the public key pinned in this
checkout. Obtain that checkout/key through a trusted path. The key copy in
the download is a convenience, not a new trust anchor.

The final artifact contains three archives, `manifest.json`, its detached
`manifest.json.minisig` signature, and the public key. Intermediate platform
artifacts are diagnostic; only `verified-signing-smoke` represents the complete
verified set. Artifacts expire after 14 days.

The manifest binds the source SHA, workflow run/attempt, target names, file
names, lengths, and SHA-256 hashes of final packaged bytes. Its schema and
`signing-smoke-only` purpose distinguish it from a future product manifest.
It is not a version-selection or anti-rollback protocol for an updater.

## Release environment

Configure an Actions environment named `release`, with a custom branch policy
permitting only the `main` branch. No recurring approval gate is required.
That policy must also be configured in GitHub; YAML cannot create it.
Concrete publisher/account values belong in the environment, never in source.

| Secret | Source / purpose |
| --- | --- |
| `MACOS_CERTIFICATE_P12_BASE64` | Existing Developer ID certificate/private-key export, base64 encoded |
| `MACOS_CERTIFICATE_PASSWORD` | Export password |
| `MACOS_KEYCHAIN_PASSWORD` | Random disposable CI keychain password |
| `ASC_API_KEY_P8_BASE64` | Existing notarization API key, base64 encoded |
| `ASC_API_KEY_ID` | Matching key identifier |
| `ASC_API_ISSUER_ID` | Matching issuer identifier |
| `AZURE_CLIENT_ID` | Existing signing application identifier |
| `AZURE_TENANT_ID` | Signing tenant identifier |
| `AZURE_CLIENT_SECRET` | Existing signing application's secret value |
| `RELEASE_SIGNING_KEY` | Dedicated Machine Control minisign secret-key contents |

| Variable | Purpose |
| --- | --- |
| `MACOS_SIGNING_IDENTITY` | Full Developer ID Application identity |
| `APPLE_TEAM_ID` | Expected signing team |
| `AZURE_SIGNING_ENDPOINT` | Artifact Signing service endpoint |
| `AZURE_SIGNING_ACCOUNT` | Signing account |
| `AZURE_CERTIFICATE_PROFILE` | Publisher certificate profile |
| `WINDOWS_SIGNER_NAME` | Exact expected Authenticode certificate simple name |

The package key is independent of consumer updater keys. This workflow accepts
a minisign key generated with `-G -W`: GitHub encrypts the stored Actions
secret; its external local backup must remain in a private mode-0600 file.
Keep the backup locator in private infrastructure documentation. Never
regenerate this key during builds or overwrite another application's key.

Populate secrets with `gh secret set NAME --env release`, using interactive
input or stdin from the documented private source. Do not transfer existing
secrets through CI logs/artifacts. Private locators and deployment receipts
belong outside this public repository.

## Validation and evidence boundary

Windows verifies native MSVC execution, Authenticode chain/publisher/timestamp,
and signed execution. macOS verifies a native C bundle and nested helper,
inside-out Developer ID signing with hardened runtime, notarization, stapling,
Gatekeeper, strict signatures, and signed execution. Linux verifies native
execution and authenticates its archive through the signed manifest.
Finalization requires all platforms and verifies the complete signed manifest
with the pinned public key before uploading the final artifact.

Signing secrets enter through step inputs/environment; temporary key material
stays outside artifact directories and is removed on exit. Actions are pinned
to upstream commits. Notarization has a bounded wait; any refusal or timeout
prevents finalization.

```bash
actionlint .github/workflows/signing-smoke.yml
python3 -m unittest discover -s tests/release -v
bash -n release/sign-macos-smoke.sh
```

Tests use disposable keys and reject modified manifests, wrong keys, modified
payloads, missing platforms, and wrong source/run identity. Native builds run
on matching hosts. A passing smoke does not establish resident functionality,
permissions, installation, upgrades, Intel macOS, or ARM64 Windows/Linux.
