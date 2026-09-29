# Tactical 048: Linux Rebuild And Credential Handoff

Status: complete, 2026-09-29. Topics: `linux-resident-control`.

## Objective And Boundaries

Recreate the explicitly disposable Linux appliance for installed product tests,
with a canonical local password file and discoverable private registry locator.
The user authorized recreation after a missing credential handoff and stale
manual-unlock guidance blocked testing. Preserve other VMs and controller work.
No credential value or private machine identity enters public evidence or Git.

Use the existing official Ubuntu cloud-image factory and exact-identity claims.
Retire only the explicitly replaced stopped disposable target and provision a
fresh candidate; preserve all other domains and disks.
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

## Provisioning Evidence

The official Ubuntu amd64 image fetched from the current Noble cloud-image
route matches its published SHA-256
`6a81c37564db9b1ee84e141922625e1d7c5b389b99bb3c572e0243607d5bb4d2`.
Factory preflight passes QCOW2, private key-only CIDATA, KVM pool and unused
destination checks. The precreation common escape incorrectly requires an
existing claim; use the documented platform `bin/linuxvm factory-create`
precreation entry point, then pin the new UUID and acquire its own common claim.
No claim enforcement is disabled for an existing VM.

Cloud-init 26.1 provisions Ubuntu 24.04.5 x86_64 / glibc 2.39 / GNOME 46 and
reboots. The initial `ensure-ready` startup deadline expires while cloud-init
is still installing the desktop; factory stages correctly remain waiting.
Do not interpret that as a completed guest needing arbitrary repair.
Normal development bootstrap then passes its package/service audit and full
resident doctor. Fresh-profile idle locking is disabled and idle delay is zero.

The canonical mode-0600 password file under a mode-0700 directory is registered
in the private inventory before use. The independent guest-agent channel pins
the exact guest SSH host key; authenticated key-only setup streams password
bytes to `chpasswd` over stdin. A separate guest shadow-hash comparison verifies
the stored value without returning the hash/password, and repeats successfully
after reboot. SSH reports `PasswordAuthentication no`. This is credential
persistence verification, not a GUI lock-screen/PAM unlock qualification.
The factory transition from cloud-init networking to NetworkManager changes
the DHCP address; rediscover it through the common target instead of reusing
the pre-reboot address.

Builder `python3 bin/check --portable` passes. Claimed Linux `tests/smoke.sh`
passes native semantic effects, exact-window capture, virtual HID, application
lifecycle, guest file round trip and outer-input refusal. Source changes are
documentation only. Temporary seed detachment, promotion and cleanup pass as
recorded below.

## Promotion, Recovery Limit And Final Handoff

Retire the replaced stopped target only after checking its pinned identity,
absence of snapshots, exact disk and absence from every other domain's backing
chain. All other domain identities remain present. Promote the new exact target
and retained setup-key/password locators in private inventory; its 14 inventory
unit tests pass. Preserve the unrelated private SSH configuration edit.

Serialize lifecycle transitions: wait for common shutdown to finish before
seed detachment, then call `target ensure-ready`. Overlapping guest probes in
the first attempt could start the guest again, and seed removal correctly
refused a running target. The serialized repeat stops in 4.937 seconds, detaches
all seed media and becomes fully ready again in 14.279 seconds. Verify the stored
password after restart; metadata readiness alone remains insufficient.

Consuming RSTorrent tests then pass a private 32-MiB transfer, real test-browser
closure/restoration, native tray lifetime, explicit Quit without passive
resurrection, deliberate relaunch and a published signed AppImage update.
Product commands, hashes and limitations belong in RSTorrent 238/239, not this
control repository. The fresh browser's GNOME keyring-creation dialog initially
blocks networking; cancelling it suffices, without creating another credential.

One guest sleep experiment is **not qualified**. The RTC alarm-only precheck
passes, but guest `rtcwake -m mem -s 20 -u` does not restore administration or
resident connectivity. The virtual machine remains running; no successful
suspend-exit receipt is available. Stop pending owned probes, use the guarded
common `testbed -- force-stop`, then `target ensure-ready`; it returns fully
ready in 14.235 seconds. This is recovery from a failed experiment, not supported
native sleep/wake or a product regression diagnosis. Do not repeat this route
without a qualified recovery path. The consuming test repeats independently
with fresh fixtures outside the boot-cleared temporary tree.

Final cleanup removes owned guest apps, test browser/sandbox, profiles,
registrations, payloads, six capture artifacts and test staging. The controller
server/seed, exact task firewall rules and captured artifacts are removed;
builder caches remain. A final doctor reports every resident surface ready.
The mode-0600 canonical password again matches the guest account, SSH password
authentication remains disabled, and `inventory credentials` with the inventory
ID reports ready. Inventory IDs and logical target names need not be identical.
Common shutdown reaches off in 4.870 seconds and claim release succeeds.
The recreated VM, setup key, pinned host key and registry-linked login password
are retained for future tests. No secret value or private endpoint enters Git.

Exact public command shapes used: `bin/machine-control inventory credentials
<inventory-id>`, `target doctor`, `claim acquire`, documented Linux
`factory-create`, `testbed -- factory-stages`, `target ensure-ready`, development
bootstrap, `python3 bin/check --portable`, claimed `platforms/linux/tests/smoke.sh`,
`testbed -- factory-detach-media`, `target shutdown`, and `claim release
<claim-id>` without an already-selected global claim. Concrete inventory,
identity, setup keys and credentials remain in private controller state.
