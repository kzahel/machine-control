# Tactical 049: Linux Credential Promotion Gate

Status: implementation complete with deterministic validation, 2026-09-29.
Topics: `linux-resident-control`, `target-lifecycle-and-readiness`,
`operational-workflow-automation`.

## Objective and completion conditions

The user requested the recommended updates after discussing how key-only
bootstrap, auto-login and operational tests allowed a Linux appliance to be
accepted without a usable stored login password. Make credential handoff a
checked completion condition instead of relying solely on agent instructions.

Completion requires deterministic proof that missing/unverified credentials
block factory promotion and common promotion preparation, verification precedes
shutdown, stopped handoff rechecks the private evidence, and secrets remain
outside arguments, ordinary JSON and evidence. Update the owning guides and
topics, run portable/static checks, then commit and push. Live guest acceptance
of the new verifier is explicitly separate from implementation completion.

## Boundaries

Linux appliance setup/administration owns this operation. Do not implement GUI
unlock, relax guest authentication policy, change other platform promotion,
set/reset passwords implicitly, or edit private inventory from the common client.
Keep the password profile as the default. A password-free appliance requires an
explicit profile and proof of a locked exact-account password entry.

## Ordered work

### 1 — verify the canonical credential

Add claimed `credential status|verify`. Require exact UUID and account before
secret consumption. For password verification, check owner-only file metadata,
discover the guest address and ED25519 host key through exact guest administration,
compare the independently pinned known-hosts entry, then send bytes only over
dedicated key-only SSH stdin. Compare the guest shadow hash with libcrypt and
return only a fixed verification result; reject locked/expired password accounts.

Write an atomic private mode-0600 receipt bound to provider, UUID, account,
profile, locator and file metadata with a 24-hour lifetime. Status consumes no
password bytes. Failed guest rechecks invalidate previous evidence. Receipts
cannot detect unobserved guest-side changes continuously.

### 2 — gate provisioning completion

Add credential and promotion stages to both Linux factory inspectors. Require
fresh verification before common `prepare-promotion` shutdown and a matching
receipt after the exact stopped assertion. Preserve operational doctor/readiness
and validation during bootstrap. Replace the locked-desktop `human_required`
classification with credential discovery guidance; no secret delivery capability
is inferred for the GUI.

### 3 — prove refusals and document the handoff

Exercise missing locators, mismatched identity/host key, unsafe file permissions,
stale/configuration-changed receipts, password rotation, verification failure,
explicit password-free behavior, both factory providers and common pre/post-stop
gates. Add Linux dependency-free tests to the portable runner and a static smoke
entry point for verification without operating a VM.

## Validation and final result

`python3 bin/check --portable` passes, including the newly registered 33-test
Linux factory/credential/maintenance suite and common promotion regressions.
`bash platforms/linux/tests/smoke.sh --static` passes. ShellCheck at warning
severity passes for the touched shell files, and both Linux UTM Swift helpers
typecheck without warnings. `git diff --check` passes and 105 local document
links resolve in the reviewed guides/topics/tacticals.

The new gates refuse missing/unverified credential evidence, uncertain identity
or host key, unsafe secret permissions, changed/expired receipts, and failed
guest rechecks. Tests execute the guest verifier with synthetic account/libcrypt
fixtures to distinguish correct, mismatched, locked, expired and forced-change
password entries. Common preparation refuses before shutdown on verification
failure and never reports eligibility after a failed stopped receipt recheck.

No real appliance was created, re-credentialed or operated by this slice; live
setup SSH and guest verifier acceptance are not claimed. Hash equality is not
GUI/PAM unlock acceptance. Existing private locators must be configured through
the documented handoff before the stricter Linux promotion path can pass.
