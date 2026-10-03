# Native desktop delegation

Status: active; MC receiver foundation implemented, upstream YA proof pending.
Owning topics: [caller authorization](../../topics/caller-authorization.md) and
[access admission and pause](../../topics/access-admission-and-pause.md).
Dependency: [trusted Desktop access](071-desktop-caller-authorization.md).

## Objective and completion conditions

Authenticate the native YA broker, bind each finite intent to a selected live
session, and preserve Pause/Stop semantics without treating public labels as
bearer authority. Complete only after actual signed YA launch provenance,
negative callers, lifecycle cleanup and installed effects pass.

## Boundaries

The first automatic profile permits only the ordinary local unlocked desktop.
It cannot unlock, arm protected use, invoke native sudo, select outer recovery,
or reach a remote target. Existing explicit target-wide access remains an
explicit cooperative legacy profile; it is never a fallback for a denied
request carrying delegated-session attribution. No same-user shell containment
is claimed. Trusted integration is default off and independent of OS grants.

## Ordered work

1. Implement native MC peer authentication, private durable trust/Stop policy,
   connection/revision-bound authority, bounded attribution and refusal gates.
2. Add the actual YA native broker and a private inherited duplex channel to
   its bundled server. Validate the sealed code/resources and disallow source,
   permissive-auth or detached-provider configurations for automatic access.
3. Bind delegation to authenticated eligible session creation and actual
   provider launch. Register exact process identity/lifetime privately; a
   public label or ancestor match alone cannot authorize a caller. A private
   agent proxy may use kernel ancestry only against those registered launches.
4. Route the installed CLI through that proxy with no fallback after delegated
   authentication failure. Keep transport loss/uncertain mutation non-replayable.
5. Expose native opt-in/trust removal and selected YA session controls behind
   capability negotiation. Stop suspends automatic authority across restart.
6. Qualify signed native YA positives plus unrelated processes, signed Bun,
   forged/cross-session labels, stale PIDs/generations, private channel loss,
   transport/MC restart, scope reduction and Stop. Prove independent effects.

## Current receiver result

**Current, source implemented:** an additive `desktopDelegation` open frame
requires enrolled specific native identity. MC reads the kernel audit token,
checks dynamic strict code validity/designated requirement and the sealed app
bundle before issuing connection authority. Enrollment validates the intended
YA identifier, publisher-backed signature and explicit delegation protocol.
Dynamic identity is checked again before activation/dispatch; queue inspection
does not repeatedly hash the entire resource bundle. Runtime revisions and
finite admission generations fence old connections. No session or queue is
restored from disk.

Trust is stored as a bounded UID-private regular file, with no-follow reads,
hard-link refusal, atomic replacement, file/directory fsync and a fresh runtime
revision. Failed persistence removes old authority and fails closed. Stop keeps
trust suspended; only operator enrollment enables it again. The setter is on
the private native operator surface, not the public agent socket.

**Current, fixture evidence:** 135 Swift checks pass without warnings, including
real socket delegated effects with no ambient grant, foreign-delegate refusal
despite ambient access, Pause/fresh Resume, protected/outer denial and persistent
Stop/reconnect. Store fixtures cover links, invalid booleans, restart, reduction
and failed Stop persistence. Unsigned native enrollment/peers refuse. The native
Desktop bridge compiles; source-native deploy/doctor and static checks pass.
These positive receiver tests inject fixture admission; they do not prove YA
session origin or a signed native YA connection.

**Open:** steps 2–6. No YA changes or automatic trust UI have been delivered by
this receiver commit. Current released YA has no delegation protocol and is
refused for enrollment. Do not advertise authenticated production integration
or mark either coordinating plan complete on this foundation alone.
