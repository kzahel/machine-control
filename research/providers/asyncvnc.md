# AsyncVNC

Upstream: [barneygale/asyncvnc](https://github.com/barneygale/asyncvnc).

Declared license: GPL; the tested distribution includes the GNU GPL version 3
license text. Treat it as GPL-3.0 software, not an MIT code donor. No narrower
component or dependency license audit has been completed for distribution.

Last corpus review: 2026-09-10.

## Evidence

| Platform / route | Level | Evidence and limit |
| --- | --- | --- |
| macOS Screen Sharing | `source-reviewed`, `live-tested` | Headless authentication, capture, keyboard, pointer, stock lock/password unlock, and guest consent bootstrap in a SIP-enabled disposable Tart guest |
| Other VNC servers / platforms | `upstream-claimed` | General RFB support; not exercised in this investigation |

The [SIP investigation](../../docs/tactical/033-macos-sip-authorization-unlock.md)
owns the bounded live result. Exact installed-package details and temporary
client code remain in private experiment evidence. No AsyncVNC source was
copied into the owned authorization plug-in or installed resident.

## Architecture and depth

AsyncVNC is a Python asyncio RFB client. It supplies pixel frames, keyboard,
pointer, and clipboard operations, including an Apple username/password
authentication route. It does not itself supply Accessibility semantics,
application identity, session grants, or independent action-effect evidence.
The server determines privilege and session reach.

Connecting to macOS's own Screen Sharing service is remote access to a
target-resident provider. It is distinct from connecting to Tart's optional
hypervisor VNC server. A headless client can avoid opening a controller-host
window or injecting through the host desktop. The tested wrapper checked the
common exact-target claim before each operation and kept its credential in
the disposable target's private manifest.

One capture timed out after a session transition; reconnecting while unlocked
restored capture. Frame pixels and native display points differed by a factor
of two in the tested guest, so their coordinate spaces must remain explicit.
The client was disconnected before the owned plug-in's integrated unlock
tests to exclude remote authentication as the cause of an unlock.

## North Star fit and gaps

**Current:** Useful temporary access to an already-enabled native macOS service
for consent/bootstrap without controller-desktop interference. It is not an
adopted Machine Control adapter or a common semantic provider.

**Open:** A retained integration needs an explicit packaging/license decision,
server identity and transport policy, session-transition handling, coordinate
normalization, typed claim enforcement, and independent effect checks. The
live bootstrap result does not establish personal-Mac security containment or
all protected-screen behavior.
