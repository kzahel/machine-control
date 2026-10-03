# Mac helper permission and locked-use preference

Owning topic: [macOS locked use](../../topics/macos-locked-use.md).

Status: implemented; native setup and covered completion verified in the VM.
Physical acceptance remains open.

## Objective

The person requested that the locked-use checkbox reuse setup completed in
Permissions and never request a new grant. Replace its command/password prompt
with Apple's System Settings service approval. Existing Accessibility and
Screen Recording grants remain the desktop prerequisites; they cannot install
an authorization plug-in themselves.

## Completion conditions

- Permissions owns native helper registration, approval, repair, and capture
  preparation. System Settings owns authentication; the app reads no password.
- The Settings checkbox only persists the preference and revokes active use
  when disabled. Missing preparation sends the person to Permissions.
- Helper preparation leaves locked use off and grants no ordinary access.
- Preserve typed privileged operations, code/session binding, policy-conflict
  refusal, ordinary password fallback, bounded use, and failure relock.
- Build and validate the source and signed bundle; record live evidence
  separately from remaining physical acceptance.

## Boundaries

No invented macOS privacy category, reuse of TCC as root authority, SIP change,
password storage, arbitrary privileged command interface, or closed-lid support.
The appliance installer remains an explicit administrator tool. The workstation
helper uses SMAppService and an app-bundled daemon instead of a sudo dialog.

## Ordered work

### 1 — separate permission preparation from the preference

Make the setting side-effect-free with respect to installation and permission
requests. Keep Permissions status and actions in the native operator boundary.

### 2 — register the helper with macOS

Bundle its daemon property list, request Apple's service approval, and wait
for observed approval before fixed, authenticated plug-in setup. Reuse the
root watchdog and conflict-aware installer through closed typed operations.

### 3 — verify the new setup and covered-use path

Test preference/permission separation, build both native architectures, inspect
the signed app layout, and use the claimed VM before another physical lock.
Native consent and manual recovery on a personal Mac remain person-owned.

## Result

The checkbox only changes the prepared preference. Permissions owns service
registration, native System Settings approval, repair, removal, and capture
preparation. Root preparation admits only the signed operator in the registered
bundle and a matching unlocked console. It pins the running generation's code
and executes a verified payload copied into root-private storage, with bounded
child lifetime and cleanup. Public resident requests cannot arm preparation.

Validation: 61 Swift tests passed, including permission-free on/off/on toggles,
unprepared refusal without a setup request, and preparation leaving use off.
TypeScript checking, ARM64 and Intel helper builds, an Intel resident bundle,
and the ARM64 Tauri bundle passed; the assembled candidate was Developer ID
signed and verified with deep strict code validation.

Live evidence: in the dedicated one-display macOS 26.6.2 VM with SIP disabled,
Permissions reused existing Accessibility/Screen Recording grants and opened
Login Items & Extensions for OS-managed approval. The strict native one-shot
credential route observed dismissal of Apple's Login Items sheet. Preparation
produced a healthy helper while locked use and ordinary access stayed off.
Native Settings on/off/on reused the same helper generation with no grant or
setup request. Separately approved covered completion observed AX, pointer,
keyboard, capture exclusion, and OS relock. Stored-credential manual recovery
then succeeded. Native Permissions removal disabled the preference, restored
normal password fallback, removed the plug-in, and unregistered the service.
The final root-private staging revision also passed setup/removal. The original
appliance policy and power state were restored, with exclusive claims released.

This revision does not claim SIP-enabled covered acceptance, physical acceptance,
multiple displays, closed lids, notarization, or published distribution. The
signed candidate is available for the physical test after native setup.
