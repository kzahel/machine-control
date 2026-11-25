# Windows desktop updates strand the UAC helper

Topic: `windows-desktop`

Status: **Fixed in source — production-signed installer acceptance is tracked in
[Tactical 169](../docs/tactical/169-windows-desktop-helper-upgrades.md).**

## Observations

Permissions reported **Installed** under **UAC and elevated apps**. Enabling
**Allow UAC and elevated app control** in Settings asked the operator to
install the helper. Read-only inspection confirmed that the helper service
was running and its executable differed from the 0.7.5 bundled executable.
Running the app's read-only resolver confirmed it selected the bundled copy.

The [per-user NSIS installer](../desktop/native/windows-installer-hooks.nsh)
updates the desktop app and its bundled runtime. The optional LocalSystem
service has a separate administrator-owned copy. When the executables differ,
the [resolver](../src/MachineControl.Windows/DesktopUacSetup.cs) uses the
bundled copy and the [UAC enable check](../src/MachineControl.Windows/DesktopUacClient.cs)
refuses it. The same mismatch can make covered unlock unavailable because
[its readiness check](../src/MachineControl.Windows/DesktopLockedUse.cs)
requires the installed companion. Covered unlock was not exercised in this
incident. The documented remove/install workaround erases existing unlock
enrollment. Unlock setup has a separate path that can replace the helper
while preserving enrollment, but requires operator intervention.

## Proposed repair

[Tactical 169](../docs/tactical/169-windows-desktop-helper-upgrades.md) records
the implementation and initial VM evidence. The Windows installer can restore
the previous protected payload if activation fails. Ordinary desktop use
remains available on the newly installed app, which reports the remaining
helper mismatch.

Make maintenance of an **already installed** helper part of the signed
Windows desktop update. Offer a one-time native administrator approval to
migrate existing helpers in place, keeping their encrypted unlock enrollment.
Fresh installs without the optional helper still require explicit setup.
Once migrated, the administrator-approved maintenance code updates the helper
without a separate prompt during **Install and restart**. Use the same path
for a signed installer run directly.

- Keep the exact desktop/helper build check. The privileged maintenance
  code uses Machine Control's release signing trust to verify the product,
  architecture, upgrade version and hashes of the complete payload in
  administrator-owned staging before running or activating any incoming code.
  Extend the existing [signed runtime catalog](../release/windows-desktop.md#signed-candidates)
  with authenticated release metadata as needed. The per-user installer requests
  a bounded product update. Service configuration and executable selection stay
  on the administrator side of that boundary.
  See [Windows signature verification](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/nf-wintrust-winverifytrust)
  and [Windows service permissions](https://learn.microsoft.com/en-us/windows/win32/services/service-security-and-access-rights).
- Use the existing update exclusion to drain tasks, including any pending
  protected relock. Stage versioned payloads and switch only after
  verification. Keep the previous known-good helper available through the
  health check and restore its service configuration on a failed start.
  Preserve enrollment and show a repair action for any remaining mismatch with
  the new app. An older per-user copy cannot downgrade the machine-wide helper.
- Keep enrollment and covered-access preferences separate from replaceable
  files. If UAC control was enabled, carry that choice only across the
  deliberately initiated update via an authenticated, one-shot native
  handoff bound to the incoming build. Restore the choice before ordinary
  access is restored. Ordinary launches still start UAC control off. End
  existing tasks and pending approvals at the update boundary. A failed
  handoff leaves UAC control off.
- Show **Not installed**, **Ready**, **Update required**, **Updating**, or
  **Repair needed** in Permissions. Settings should take the operator to
  the matching action instead of asking them to install an existing helper.

macOS already has signed-update maintenance for an approved helper
([Tactical 072](../docs/tactical/072-macos-helper-update-maintenance.md)).
Linux uses Debian package-owned helper files and
[erases enrollment on removal](../desktop/scripts/linux-deb-prerm.sh),
with no Windows-style executable-copy check. Keep the upgrade acceptance
expectation common and use the native maintenance path on each platform.

## Acceptance

Use exact signed x64 and ARM64 packages. Prove the one-time migration from a
legacy helper, then a second release-to-release update with no helper prompt,
reinstall, or password entry. Exercise both **Install and restart** and a
direct launch of the signed installer. Prove an approved UAC operation and,
with existing enrollment, covered unlock and relock afterward. Exercise helper
absent, UAC choice off, tampered payload, downgrade, interrupted replacement
and failed service health. Verify enrollment survives and stale owners cannot
act. Extend the
[installed Windows update harness](../tests/windows/README.md#installed-update-and-browser-acceptance)
with these cases.
