# Tactical 048: Linux Rebuild And Credential Handoff

Status: active. Topics: `linux-resident-control`.

## Objective And Boundaries

Recreate the explicitly disposable Linux appliance for installed product tests,
with a canonical local password file and discoverable private registry locator.
The user authorized recreation after a missing credential handoff and stale
manual-unlock guidance blocked testing. Preserve other VMs and controller work.
No credential value or private machine identity enters public evidence or Git.

Use the existing official Ubuntu cloud-image factory and exact-identity claims.
Create a fresh candidate before retiring the old stopped disposable target.
The existing NoCloud seed is key-only: retain that bootstrap contract, then set
a local login password through an authenticated setup SSH session using stdin,
with the canonical owner-only file as its only source. Keep SSH password login
disabled. Pin the guest SSH host key independently through guest administration.
Verify the stored password against guest authentication without logging it;
metadata readiness alone is not proof of a matching guest password.

## Ordered Work And Stopping Condition

1. Doctor and claim the old target; record its stopped state and prior cleanup.
2. Generate a canonical mode-0600 secret under a mode-0700 directory and add
   only its locator to private registry. Preserve unrelated inventory changes.
3. Verify official image checksum, render seed, run preflight, create and pin
   the candidate, doctor/claim, then use supported stage/readiness/bootstrap.
4. Install and verify the password, retain key-only SSH, detach seed and prove
   resident semantics/capture/input plus restart readiness. No UI-unlock
   capability is inferred from setup/password verification.
5. Promote the verified target in private inventory, retire only the explicitly
   replaced disposable target, and retain the credential for future use.
6. Run consuming-repository product tests separately; remove owned test state,
   stop the recreated appliance, and release claims. Record exact evidence.

Read official cloud-init user/password documentation and the factory source.
Use the documented fresh-appliance auto-login and disabled idle-lock profile;
this is provisioning, not alteration of an inherited workstation's lock policy.
Completion requires a usable replacement, verified credential handoff and
cleanup; RSTorrent update/recovery results belong in its Tacticals 238/239.
