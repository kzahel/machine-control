---
title: Why app-development agents need a machine layer
description: Coding agents can edit portable source, but testing the resulting application still crosses operating systems, VMs, UI frameworks, sessions, and recovery paths.
publishedAt: 2026-08-25
category: Architecture
readingMinutes: 8
draft: false
---

A coding agent can change a cross-platform codebase in one checkout. The built
application is less cooperative. It may need to be installed on Windows,
launched under a real macOS user session, inspected through Linux accessibility,
or exercised on a physical phone. Each target has its own lifecycle, native
automation facilities, permissions, and ways to fail.

The usual response is to give the agent a collection of unrelated scripts—or
reduce every target to screenshots and coordinates. Both approaches work for a
while. Neither gives the agent a durable model of the machine it is testing.

Machine Control is an attempt to provide that missing layer.

## The development problem, not the demo problem

The interesting workflow is not “make an agent click a button.” It is:

1. build a real application;
2. select the right operating-system target;
3. acquire exclusive or isolated use of it;
4. deploy and launch the build;
5. inspect the actual application and system UI;
6. perform a bounded action;
7. observe whether the intended effect occurred; and
8. retain useful evidence and clean up the target.

That loop matters for projects with real platform surfaces: installers,
application menus, file associations, permissions, background services,
updaters, tray or Dock behavior, mobile lifecycle, and protected system UI.

Browser automation remains excellent when the system under test is a web page.
A shell is usually best for files and processes. Direct application APIs are
best when they exist. The machine layer is for the part of development where
those clean interfaces meet a running operating system.

## One interface does not mean one implementation

Windows UI Automation, macOS Accessibility, Linux AT-SPI, Chrome accessibility,
XCTest, and ADB do not expose identical worlds. Flattening them into one
lowest-common-denominator driver would discard the reason to use them.

Machine Control instead shares the parts of the workflow that should be stable:

- target selection and capability discovery;
- readiness diagnostics, claims, and workspaces;
- application, window, observation, action, and capture vocabulary;
- provider route and host-interference reporting; and
- delivery, effect, evidence, and uncertainty.

The adapter still reports the real provider. A Windows action can say it used
UIA; a macOS action can say it used AX. A platform-specific operation remains
explicit when projecting it into a generic desktop shape would be misleading.

## Compact state is infrastructure

Repeated screenshots are expensive observations. Large accessibility trees can
be nearly as wasteful if every poll returns the same provider detail.

The common desktop contract therefore supports compact semantic projections and
content digests. Compact output retains useful roles, labels, values, states,
bounds, actions, and hierarchy while omitting noise. When the digest has not
changed, the next observation can return that fact without sending the element
tree again.

Current Windows fixture measurements are deliberately modest evidence, not a
grand token claim. Calculator measured 9,971 bytes for a full observation,
6,577 bytes for compact, and 1,165 bytes when unchanged. Settings measured
4,971, 3,843, and 986 bytes respectively. A useful next benchmark will measure
model input tokens and task completion across screenshot, full-semantic, and
compact-digest workflows on several targets.

## A successful call is not a successful test

Input delivery is not application effect.

A provider may report that it clicked a checkbox even though a modal intercepted
the action. A text injector may return successfully while the field value stays
unchanged. A transport failure after dispatch may leave the outcome genuinely
unknown.

Machine Control keeps those states separate. Results report whether the request
was accepted, whether delivery was confirmed, what effect was observed, what
evidence supports that conclusion, and whether retrying would be safe. This is
less convenient than returning `success: true`; it is much more useful for an
agent deciding what to do next.

## Remote control should still happen on the target

An agent outside a VM should not need to focus a hypervisor window on the
developer’s desktop and type through it. Ordinary application control should
use the same target-native route whether the caller is local or reaches the
resident through an authenticated transport.

Hypervisor consoles, hardware KVMs, and host-side input remain valuable for
bootstrap, independent observation, and recovery. They are different routes
with different consequences. Machine Control makes that distinction visible
and prohibits silent escalation from an inner operation to a disruptive outer
one.

## What exists today

Windows, macOS, and Linux share an exercised desktop contract for status,
capabilities, applications, windows, semantic observations, actions, capture,
artifacts, workspaces, and claims. Windows is the first complete vertical
slice. ChromeOS, iOS, Android, Quest, and Steam Deck have working native routes
at different levels of common-facade coverage.

The project is active and pre-1.0. The schemas are evolving. The claim is not
that every machine is solved; it is that cross-platform app development needs a
stable, evidence-driven machine boundary, and that enough of that boundary now
exists to exercise real software.

Machine Control is [MIT-licensed and developed in public](https://github.com/kzahel/machine-control).
