---
title: From a ChromeOS testbed to agent-native development
description: Machine Control began as a ChromeOS testbed. It became a cross-platform machine layer that lets one agent develop across VMs and physical devices.
publishedAt: 2026-08-25T15:30:00Z
category: Project story
readingMinutes: 6
draft: false
---

Machine Control did not begin as an attempt to design a universal computer
automation framework. It began because I needed a coding agent to test an
application on ChromeOS.

I work on applications that cross the usual platform boundaries. A feature may
share most of its implementation across desktop, browser, and mobile builds,
but the finished application still has to run inside the real operating system.
It has to install, launch, interact with system UI, survive lifecycle changes,
and behave correctly on the hardware people actually use.

ChromeOS exposed the gap first.

## The original ChromeOS problem

There was no testbed harness that gave an agent the control surface I wanted on
a real Chromebook. Browser automation could operate a page, but the application
work also crossed the ChromeOS desktop, application windows, device lifecycle,
and system state. A remote desktop could expose pixels and input, but it did not
give the agent a compact semantic model of what it was looking at.

The original `chromeos-testbed` grew around that need. An agent outside the
Chromebook could reach it over SSH while the useful work happened on the target:

- administration and readiness checks;
- desktop semantics through `chrome.automation`;
- per-page browser control through CDP;
- target-native screen capture; and
- keyboard and pointer input generated inside ChromeOS.

The Chromebook did not need to be sitting in a visible host window. The agent
could inspect and operate the real physical device using the strongest routes
the platform provided.

That shape still matters. Remote access should not mean pretending the target
is only a stream of pixels. It should mean reaching useful control that remains
native to the target.

## Why was I still testing everything else manually?

Once the ChromeOS route worked, the larger problem became difficult to ignore.

Coding agents could make substantial changes to a shared codebase. They could
run unit tests and build several packages. But when the work crossed onto a
Windows VM, a Mac application, an iPhone, or an Android device, the feedback
loop often stopped. I would take over, install the build, navigate the UI, and
report what happened.

The missing capability was not more code generation. It was letting the agent
finish the development loop itself.

The workflow I wanted was straightforward:

1. change the application;
2. build the appropriate package;
3. select a VM or physical device;
4. reserve and prepare that target;
5. deploy and launch the build;
6. inspect and exercise the real application;
7. verify the observed effect; and
8. bring back evidence before releasing the target.

Changing from Windows to ChromeOS or iOS should change the route and the
available capabilities. It should not require inventing a completely different
agent workflow.

That realization turned the ChromeOS testbed into Machine Control.

## One session does not mean one lowest-common denominator

The goal is one target-oriented experience, not one shallow automation driver.

Windows has UI Automation and deeper Win32 routes. macOS has Accessibility,
Workspace, and CoreGraphics. Linux has AT-SPI and compositor-specific capture.
ChromeOS exposes desktop accessibility and per-page CDP. Physical iOS devices
use CoreDevice and XCTest from an authorized Mac. Android begins with ADB and
its native automation facilities.

Machine Control keeps those differences visible. It normalizes target
selection, readiness, claims, workspaces, observations, actions, capture, and
results while reporting the provider that actually performed an operation.
Platform-specific capabilities remain platform-specific when flattening them
would be misleading.

The result is broad control without pretending every machine is the same
machine.

## VMs and physical devices are both essential

Desktop VMs are excellent development targets. They are repeatable, isolatable,
and easy to return to a known state. Machine Control currently supports live VM
controller hosts on macOS and Linux, with a Windows Hyper-V host route planned
next.

Physical devices solve a different class of problem. A real Chromebook, iPhone,
Android phone, headset, or handheld exposes hardware, drivers, security
boundaries, sleep and wake behavior, input devices, and lifecycle conditions
that a simulator cannot prove.

The agent should be able to choose either kind of target from the same session.
Whether the route reaches a VM resident, a physical Chromebook, or an XCTest
runner on an attached iPhone is an implementation and capability distinction—not
a reason to hand the work back to a person.

## How I use it now

Machine Control now supports development and testing across the applications I
ship through [Graehl Arts](https://graehlarts.com):

- [JSTorrent](https://jstorrent.com), across browser, desktop, ChromeOS,
  Android, and iOS surfaces;
- [RSTorrent](https://github.com/kzahel/rstorrent), with Rust-backed desktop and
  mobile clients;
- [Atpiano](https://at-piano.com), with native macOS and Windows packaging and
  UI workflows; and
- [200 OK Web Server](https://ok200.app), across desktop, Android, and ChromeOS.

The useful unit is no longer “an agent wrote a patch.” It is “an agent changed
the feature, visited the relevant environments, operated the application, and
returned with evidence about what actually happened.”

That is what I mean by **agent-native cross-platform development**. The agent
is not only present for code generation. The machines and devices are part of
its development environment.

Machine Control is active and pre-1.0. The interfaces and coverage are still
evolving, and each platform has honest limitations. But the project has already
moved beyond the original Chromebook problem: one coding session can now reach
the real targets where cross-platform software has to work.

Explore the [current platform and VM-host status](https://machinecontrol.dev/#targets),
read the [comparison with adjacent tools](https://machinecontrol.dev/compare/),
or [follow the source](https://github.com/kzahel/machine-control).
