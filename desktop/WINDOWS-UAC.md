# Windows desktop UAC control

This optional integration ships in public desktop 0.5.7 and starts disabled.
Focused unsigned x64 VM acceptance passes. Signed installed feature, ARM64 live,
physical hardware, and localized prompt acceptance remain separate gates.

## Operator setup

1. Stop access and finish any pending approval.
2. In **Permissions**, choose **Install helper…** under **UAC and elevated
   apps**, then complete Windows administrator approval. Cancelling installs
   nothing and keeps access off.
3. In **Settings**, select **Allow UAC and elevated app control**. This choice
   starts off on each app run. Changing it stops access and requires fresh
   approval.
4. Enable the needed observation/control scopes in **Access**. The agent must
   acquire and retain a live control session through the installed CLI/SDK.

Installation alone grants no access. The desktop app and its companion remain
Medium integrity. The separate `MachineControlDesktopUac` service runs as
LocalSystem with an administrator-owned payload. It starts a protected worker
in the same active console session only for authenticated desktop requests.
It does not reuse the appliance service or inherit its authorization.

Pause, Stop, grant expiry, owner disconnection, and session loss fence protected
requests. Authority is checked before dispatch and again before native effects.
The emergency Stop shortcut remains **Ctrl+Alt+Shift+Period**. Stopping access
does not press a button on a pending UAC prompt; the operator can finish or
cancel that prompt through Windows.

## Agent behavior

Existing desktop operations reach elevated application windows through the
native protected provider while this option is enabled. Capabilities report
the actual privilege, route, supported operations, and omissions. Application
launch and registered application activation retain their Medium route.

On the secure desktop, observation is available only after discovering a
unique stock consent process and a prompt without credential fields. Generic
keyboard, pointer, typing, value changes, and semantic invokes refuse there.
The only protected prompt actions are:

```json
{"operation":"uac.respond","state":"cancel"}
{"operation":"uac.respond","state":"approve"}
```

These require a live owner with control scope and an active native grant.
Responses separate delivery from the observed return to the Default desktop;
the caller must independently check the requested application's effect.
Uncertain mutations are not replayed or rerouted. Semantic references become
stale across observed desktop transitions.

This version supports English stock consent buttons. Credential prompts,
password/Hello entry, lock/login, RDP, and other users/sessions are unavailable.
UAC and secure-desktop policy stay enabled. This is not same-user shell
containment: an unrestricted shell can request its own elevation or act under
the user's authority.

## Removal and updates

Stop access, then choose **Remove helper…** in Permissions and complete Windows
administrator approval. The app stops its companion before removal and returns
to the ordinary profile afterward. Remove this separate helper before
uninstalling the desktop app; ordinary per-user uninstall does not remove an
administrator-installed service.

An installed helper cannot silently override a newer bundled runtime. The app
uses it only when executable hashes match. After a product update, remove the
old helper and install the new one before enabling protected control again.
Other desktop instances using that payload must be closed before removal.

See [Windows desktop](../topics/windows-desktop.md) for current acceptance and
[Tactical 097](../docs/tactical/097-windows-desktop-uac.md) for the implementation
and validation record.
