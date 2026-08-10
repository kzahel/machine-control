# macOS UI Automation

## Control Order

1. Use `macvm exec` for files, processes, packages, and system facts.
2. Use `macvm control` for resident semantics, target-local capture, and
   target-local input in a logged-in desktop.
3. Use `macvm ui` for direct native Accessibility diagnosis.
4. Use host-side `screenshot`, `click`, `type`, and `key` only for initial
   bootstrap or explicitly selected recovery.

Set `MACVM_FORBID_OUTER_UI=true` during ordinary software-test conformance.
The guard rejects every host-side Tart screenshot/input operation while
leaving lifecycle and the selected guest command transport available.

## Semantic Inspection

The default application is the current guest frontmost application. Prefer an
explicit app when a task may change focus:

```bash
bin/macvm ui windows --app 'System Settings'
bin/macvm ui tree --app 'System Settings' --interactive --depth 10
bin/macvm ui find Bluetooth --app 'System Settings' --role button
```

Application selectors match localized names, bundle identifiers, or PIDs.
Element queries inspect title, description, value, identifier, role, and
subrole. Add `--exact`, `--role`, or `--nth` when a text query is ambiguous.

The traversal defaults are bounded. Increase `--depth` or `--limit` only
after inspecting a smaller tree. Some web views and custom-drawn applications
expose sparse accessibility trees; use the visual path when the owning app
does not publish meaningful elements.

Dock and menu-bar processes are addressable applications rather than excluded
surfaces. Inspect the owning process before acting:

```bash
bin/macvm ui tree --app Dock --interactive --depth 8
bin/macvm ui tree --app 'Control Center' --interactive --depth 8
bin/macvm ui tree --app SystemUIServer --interactive --depth 8
```

Whether a particular item exposes a useful element still depends on macOS and
the owning menu extra. Fall back to resident full-display capture and
target-local coordinate input when it does not.

## State-Changing Actions

```bash
bin/macvm ui actions Save --app TextEdit
bin/macvm ui press Save --app TextEdit
bin/macvm ui focus Search --app Safari --role textfield
bin/macvm ui set-value Search 'query text' --app Safari --role textfield
```

Element references printed as `@N` are ephemeral. Rediscover after navigation,
window recreation, application launch, or any action that materially changes
the tree.

## Target-local display capture and coordinates

The resident reports display bounds in global macOS points and captures in
display pixels. Retina displays therefore have distinct input and artifact
dimensions with explicit scale factors:

```bash
result="$(bin/macvm control '{"operation":"capture","scope":"display"}')"
path="$(bin/macvm artifact-fetch "$(jq -r '.data.artifactPath' <<<"$result")")"
bin/macvm control \
  '{"operation":"input.click","x":512,"y":384,"coordinateSpace":"global_display_points"}'
```

`input.move`, `input.click`, `input.drag`, and `input.scroll` post events from
the resident in the guest Aqua session. Supplying `target` first activates a
guest application. The result reports the actual CoreGraphics route and keeps
delivery separate from any observed application effect.

## Outer recovery coordinates

`macvm screenshot` returns exactly the configured Tart display size. The
coordinate system starts at the guest display's upper-left corner. Inspect a
fresh screenshot before coordinate input:

```bash
path="$(bin/macvm screenshot)"
bin/macvm click 512 384 left
bin/macvm drag 300 240 700 240
```

Coordinate clicks and drags move the host pointer and foreground the Tart
window. They are recovery operations and fail closed when
`MACVM_FORBID_OUTER_UI=true`.

## Keyboard Input

`type` sends printable ASCII, tab, and newline as physical US-keyboard events.
This remains available before the guest agent exists. `key` sends physical key
events and supports common modifier prefixes:

```bash
bin/macvm type 'hello'
bin/macvm key enter
bin/macvm key cmd-space
bin/macvm key cmd-shift-g
bin/macvm key ctrl-option-delete
```

Start the VM through `macvm up` so Tart receives `--capture-system-keys`.
Without it, host macOS may consume shortcuts such as Command-Tab or
Command-Shift-G.

## TCC And Integrity

The signed MacVM UI app requires Accessibility permission. `macvm authorize-ui`
requests the normal macOS flow; [bootstrap](bootstrap.md) records the exact
one-time setup. Do not copy, replace, or edit a TCC database.

The resident facade reports the native helper and any installed Cua provider
separately. A ready Cua route does not turn a missing native grant into
success; capabilities and operation results name the provider actually used.
An explicit `provider` request never falls back to another provider.

## Resident Requests

Use `macvm control` for ordinary agent automation. A request and response use
one compact JSON object:

```bash
bin/macvm control '{"operation":"capabilities"}'
bin/macvm control \
  '{"operation":"snapshot","target":"TextEdit","projection":"compact"}'
```

Inside the guest, `~/bin/machine-control` accepts the identical payload. A
snapshot reference belongs to the resident generation that returned it. Do
not cache it across resident or provider restart.

Provider adapters normalize application, window, semantic element, and capture
objects before returning them. Callers use `applications`, camel-case identity
fields, `role`/`label`/`reference`, and `artifactPath` regardless of whether
the result came from native macOS APIs or Cua. Compact projection removes
detail; it does not rename the public fields.

With both providers ready, the current measured default uses native macOS AX,
Workspace, Quartz, and CoreGraphics routes. Text insertion is the one adopted
Cua route: identical fixture evidence showed native Unicode key delivery
without an AppKit text-value effect, while Cua produced the value. An explicit
`provider: "macos-native"` request remains available and reports that native
behavior honestly.

The optional deterministic fixture is compiled inside the guest:

```bash
bin/macvm deploy-fixture
bin/macvm control \
  '{"operation":"application.launch","applicationId":"org.machine-control.fixture"}'
```

Its visible state is also persisted beneath the guest user's cache directory
so conformance can prove an effect independently of action acknowledgement.

## Administrator Authorization Sheets

After the resident has Accessibility permission, a normal Aqua
`SecurityAgent` administrator sheet can be controlled without Tart-window
input. Begin only after independently triggering the intended operation and
reading its context identifier:

```bash
bin/macvm control \
  '{"operation":"authorization.begin","expectedRequester":"EXPECTED APP","contextId":"OPAQUE CONTEXT","timeoutMs":30000}'
bin/macvm authorization-submit GENERATION_BOUND_LEASE_ID
```

`authorization.begin` requires one active `SecurityAgent` process, one exact
on-screen window, the expected requester and prompt text, one
`AXSecureTextField`, and unique Cancel and OK buttons. The returned lease is
bound to that process, window, requester, context, resident generation, short
expiry, and a single cancel or credential submission. A stale, expired, used,
or changed-sheet lease fails closed.

The default expiry is 30 seconds. Callers may request 250 milliseconds through
120 seconds; the upper bound accommodates an attended non-echoing credential
step without making a lease durable.

`authorization-submit` requires an interactive terminal and reads one
credential without echo. The secret travels over stdin and the resident's
mode-`0600` socket with a staged descriptor handshake; it is never a JSON
field, command argument, environment variable, file, log, capture, or result
value. The current target-local input mapping supports printable US-keyboard
ASCII. The result reports only delivery, whether sheet dismissal was observed,
the non-secret context, and uncertainty. The caller still verifies the
intended privileged effect independently.

This path does not help with the initial MacVM UI Accessibility grant because
the resident is not trusted yet. Bootstrap consent remains a direct guest-user
step. It also does not claim loginwindow, FileVault/preboot, Recovery, or
unrestricted root authority.

The same lease also recognizes the inline password window that System Settings
uses when Privacy & Security changes require administrator approval. That
variant strictly matches one active System Settings owner, exact requester and
prompt text, one secure field, unique Cancel and Modify Settings buttons, and
one untitled on-screen authorization window. It does not turn arbitrary
System Settings UI into a credential target.

## Privacy consent fixture

`deploy-privacy-fixture` installs one signed app with explicit triggers for
Accessibility, Screen Recording, Input Monitoring, Automation, notifications,
Camera, Microphone, Documents, Downloads, Full Disk Access probing, and Local
Network. `privacy-fixture-state` reads its independent file oracle. The oracle
keeps consent result, API effect, and virtual hardware presence separate. Its
Input Monitoring trigger attempts a real session event tap, and its Screen
Recording trigger probes ScreenCaptureKit content after requesting access. Its
notification trigger schedules a deterministic banner/list delivery and
records foreground presentation independently.

Use `reset-privacy-fixture SERVICE` only for classes supported by `tccutil`.
Camera, Microphone, and Automation can be reset and replayed directly. Local
Network and notification policy have no supported `tccutil` reset and must be
changed through System Settings. Full Disk Access is also settings-managed; a
protected-data failure does not itself present an Allow dialog. Never edit or
replace the TCC database to manufacture a fixture state.

Accessibility does not erase all macOS integrity boundaries. Use the outer
Tart input path for initial consent sheets that the not-yet-trusted resident
cannot reach, and for explicit recovery. After Accessibility is granted, use
the bounded resident authorization path above for matching normal Aqua
administrator sheets. Loginwindow, FileVault/preboot, Recovery, and other
unimplemented protected surfaces still require another explicitly selected
route or a user.
