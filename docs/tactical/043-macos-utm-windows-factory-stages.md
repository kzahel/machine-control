# Mac UTM Windows Factory Stages

Topics: [operational-workflow-automation](../../topics/operational-workflow-automation.md),
[windows-resident-control](../../topics/windows-resident-control.md)

Status: complete; a fresh Mac UTM candidate reached exact-source certification
and a clean stop through the staged factory route.

## Objective and completion conditions

Give the Mac UTM route the same read-only stage meanings as Linux/KVM. Preflight
must inspect official installer media, the exact Pro index, generated seed and
FAT boot media, host tools, and an unused UTM destination. The claimed report
must observe the exact VM, guest completion, removable-media order, credential,
resident, and maintenance state. Completion requires a fresh UTM candidate
advanced by stage output through certification and clean stop.

## Boundaries

The inspector never mutates a VM, reads a password value, or infers a
successful install from command delivery. The existing factory commands own
all guarded actions. Private VM identities, paths, credentials, and artifacts
remain outside Git.

## Ordered work and validation

1. Add Mac precreation probes for ISO/seed/boot shapes and UTM destination.
2. Add UTM guest-agent and removable-drive probes to the claimed report.
3. Test malformed, missing, and valid media and drive states with fixtures.
4. Advance a fresh candidate using the reported actions, diagnose any
   independently observed outer recovery boundary, then certify and stop it.

## Result

Steps 1–3 passed fixture, media-format, and existing-candidate checks. The
initial live run stopped before creating a VM because the host had about 54
GiB free. A later cleanup made enough room for step 4.

On 2026-09-28, a fresh UTM candidate used the verified public Windows 11
ARM64 ISO, the unique Pro catalog index, generated answer media, and the
read-only precreation report. First logon completed without guest input. The
claimed report observed the exact candidate, recorded its first-logon receipt,
verified key-only SSH and the stored password, and guided installer then seed
detachment. UTM reported the fixed system disk before the three removable
drives after boot; the stage guard now accepts that observed order while still
blocking unknown shapes. `tests/smoke.sh` passed after that correction.

Development bootstrap reached a ready resident doctor. Post-update audit
found a pending reboot. The first guest reboot did not return SSH within the
bound; a recovery screenshot showed the firmware boot prompt. An explicitly
claimed recovery stop and a temporary nonsecret FAT boot helper restored
Windows. The helper was removed, and a disk-only cold boot and stored-password
login succeeded. The later stage report marked all eight stages complete.

Certification first exposed a test that assumed Unix file modes on Windows;
the boot-image parser test now isolates that assumption. The full portable
suite passed inside the guest, and exact-source certification of `3ddfc83`
proved a changed boot epoch, healthy post-update audit, portable and native
checks, guest staging cleanup, and final power off. The temporary VM, media,
and credentials were then removed. The recovery was an observed exceptional
outer action, not an ordinary factory stage or proof that every reboot will
need a boot helper.
