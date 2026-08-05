# Tactical 001: Windows System-Shell Acceptance

Status: active; execution started 2026-08-05.

Topic: `windows-resident-control`

Parent tactical:
[`000-windows-resident-control-vertical-slice.md`](000-windows-resident-control-vertical-slice.md).

## Objective

Determine whether Cua Driver is a sound provisional normal-user core for real
Windows system-shell control before building the resident session and
transport proxy around it. Exercise Cua first on an existing Windows test
appliance and compare WinApp or a narrow native Windows route only where an
observed Cua gap makes the comparison informative.

The ordinary test path runs on the Windows target and is invoked through the
existing guest-administration channel. It must not require a Windows YA worker
or host-side manipulation of the VM console.

## Completion conditions

- The existing VM passes the smallest lifecycle, SSH, interactive-session,
  Cua, and WinApp health checks needed to establish an honest baseline.
- Cua is exercised against the desktop root, Start, taskbar, notification
  area, a shell flyout, Windows Settings, an ordinary dialog, and ordinary
  window management.
- Every material action records semantic observation, exact target identity,
  action delivery, independently observed effect, capture fidelity, focus and
  cursor posture, actual route, and cleanup result as separate dimensions.
- A harmless Settings change records its prior value, changes through the
  visible Settings experience, is independently verified, and is restored.
- WinApp or a native Shell/Win32 route runs on the same case only when it is an
  adopted baseline or Cua shows a material failure, omission, or fidelity gap.
- Exact commands and minimized evidence are repeatable from
  `machine-control-spike`; private target configuration and personal captures
  remain outside Git.
- The result ends with a clear decision to proceed with a Cua-centered proxy,
  change the normal-user core, or run one specifically named follow-up
  experiment.

## Boundaries

- This tactical does not build the common resident facade, protected broker,
  clean image, or image-sealing automation.
- It does not freeze a cross-platform wire protocol or make Cua's API the
  project contract.
- It does not rerun the completed general Cua fixture, integrity, lock, or
  secure-desktop investigation.
- It does not deliberately trigger UAC, lock, logout, user switching, network
  reconfiguration, account changes, security changes, or destructive state.
- Host/hypervisor screenshot and input remain recovery capabilities. They are
  not permitted as successful routes for an ordinary shell-acceptance case.
- A provider acknowledgement without a separately observed Windows effect is
  not a pass.
- Further provider research is gap-driven. Search does not continue merely to
  enlarge the candidate list.

## Acceptance cases

| Surface | Required observation and effect |
| --- | --- |
| Desktop root | Enumerate relevant top-level windows and shell surfaces without returning an unbounded tree by default. |
| Start | Open Start, inspect it semantically, search for a harmless installed application, launch it, and observe the resulting window. |
| Taskbar | Enumerate taskbar applications and activate an already-open application without host input. |
| Notification area | Identify the notification area and inspect representative visible controls without changing network, account, or security state. |
| Shell flyout | Open one harmless flyout, inspect its transient semantics, close it, and show how stale references are handled. |
| Settings | Open through both a direct administration route and the visible shell route; navigate semantically; change, verify, and restore one harmless user setting. |
| Dialog | Open, inspect, and dismiss an ordinary non-elevated Windows dialog while preserving the owning-window relationship. |
| Window state | Move, minimize, restore, maximize, activate, switch, and close a disposable application window with exact-window identity. |

The Settings case chooses its exact value only after observing the available
target state. Prefer a non-network, non-account, non-security, user-scoped
setting with an independent query and deterministic restoration path.

## Evidence record

Each case uses a compact structured record with at least:

- target, provider, operation, and actual route;
- precondition and target session/integrity state;
- observation epoch, semantic scope, and exact native-window identity;
- selector or generation-scoped reference used for the action;
- provider delivery result and timing;
- independent effect oracle and post-action semantic or visual evidence;
- focus, foreground window, z-order, physical cursor, and host-interference
  observations where applicable;
- cleanup action and independently observed restoration; and
- outcome: `pass`, `partial`, `fail`, or `blocked`, with a stable reason.

Images, full trees, and logs remain bounded artifacts. The checked-in record
contains only minimized, non-private evidence and artifact provenance.

## Implementation steps

### 1 — establish target and provider health

Run the authoritative WinVM diagnostic. Inventory the current administration,
interactive-session, Cua, WinApp, guest-local capture/input, and outer-recovery
routes without deploying new authority. Confirm the VM has not drifted from
the completed Cua spike enough to invalidate its baseline.

### 2 — make the shell run repeatable

Add a small runner and structured evidence format to `machine-control-spike`.
Reuse the exact pinned Cua build and existing guest execution path where they
remain healthy. Keep machine discovery and private configuration in the
testbed rather than the runner.

### 3 — observe shell surfaces before mutation

Inspect the desktop root, Start, taskbar, notification area, selected flyout,
Settings window, and ordinary dialog. Measure bounded scopes, reference
lifetime, exact-window linkage, and tree omissions before attempting actions.

### 4 — run reversible Cua actions

Execute the Start/application, taskbar, flyout, Settings, dialog, and window
state flows. Capture delivery and effect independently, rediscover references
after shell recreation, and restore all changed state.

### 5 — compare only demonstrated gaps

For each material Cua gap, rerun the smallest equivalent case through WinApp
or a native Shell/Win32 route. Record whether the alternative closes the gap,
changes fidelity or focus posture, or merely fails differently.

### 6 — decide the next implementation boundary

Synthesize the matrix in the Windows research report and current topic. If Cua
is adequate, name the minimum session/transport proxy to build next and the
specific adapters justified by evidence. Otherwise name the replacement core
or one bounded experiment required before that choice.

## Validation record

Execution has started. The plan and acceptance contract are recorded here;
exact commands, source pins, and live target evidence will be added to
`machine-control-spike`. Update this section with the final result and links
when the run is complete.
