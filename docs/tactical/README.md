# Implementation Tacticals

Bounded implementation plans and execution records live here.

Tacticals are selected from current [`topics/`](../../topics/README.md) and
should link the relevant [provider/platform research](../../research/README.md)
rather than embedding another candidate survey or experiment log.

Use zero-padded numeric prefixes for new tactical documents, such as
`000-topic.md` and `001-next-topic.md`. Keep one coherent implementation slice
per document. A coordinating parent tactical is acceptable when it makes the
ordering of several independently reviewable slices explicit.

Every tactical should identify:

- status: `proposed`, `active`, `blocked`, `complete`, or `superseded`;
- the owning topic or topics;
- objective and observable completion conditions;
- boundaries and explicit non-goals;
- named implementation steps in recommended order;
- validation and evidence requirements; and
- the result, deviations, and remaining work when execution ends.

Name steps for the product surface or work they cover, using headings such as
`### 3 — prove remote direct control`. Do not invent letter-and-number lane
codes that require a separate lookup table. If a step is difficult to name,
its boundary probably needs more work.

Completed tacticals remain as execution records. Continuing guidance belongs
in the owning topic and architecture documents; if they disagree with an old
tactical, update the tactical's status or add a short supersession note rather
than treating its historical plan as current truth.

When a tactical produces a related commit series, use the owning topic slug in
the commits' `Topic:` trailers and register that exact string in
[`topics.md`](../../topics.md) when the first commit is created.

## Tactical index

| Tactical | Status | Scope |
| --- | --- | --- |
| [`000-windows-resident-control-vertical-slice.md`](000-windows-resident-control-vertical-slice.md) | complete | Coordinating Windows milestone; full control, reproducible bootstrap, sustained real-app acceptance, and disposable seal verification |
| [`001-windows-system-shell-acceptance.md`](001-windows-system-shell-acceptance.md) | complete | Cua-first acceptance run across the real Windows system shell; selected a hybrid facade |
| [`002-windows-full-target-native-control.md`](002-windows-full-target-native-control.md) | complete | Full resident Windows control across ordinary, elevated, UAC, lock/login, lifecycle, and physical hardware boundaries |
| [`003-windows-credential-login.md`](003-windows-credential-login.md) | complete | Secret-safe stock PIN and password Credential Provider login from pre-login Windows |
| [`004-windows-provider-composition-and-agent-ergonomics.md`](004-windows-provider-composition-and-agent-ergonomics.md) | complete | Compose Cua and native Windows routes behind the owned facade and prove a realistic local/remote agent workflow |
| [`005-windows-clean-appliance-and-real-application-acceptance.md`](005-windows-clean-appliance-and-real-application-acceptance.md) | complete | Bootstrap a clean MachineControl-layer Windows appliance, run sustained inbox-app workflows, and verify a retained seal; source-isolation deviation recorded |
| [`006-windows-safety-launch-efficiency-and-image-factory.md`](006-windows-safety-launch-efficiency-and-image-factory.md) | complete | Fail-closed UUID target identity, native packaged-app/window control, compact unchanged-aware semantics, four-app local/remote acceptance, and a generalized-image factory with disposable OOBE proof |
| [`007-windows-iso-factory-acceptance.md`](007-windows-iso-factory-acceptance.md) | complete | Live official unactivated Windows ARM64 ISO-to-appliance acceptance through unattended Setup, resident bootstrap, product installation, and cleanup |
| [`008-macos-ordinary-session-resident-control.md`](008-macos-ordinary-session-resident-control.md) | complete | Tart-based macOS resident facade, native/Cua comparison, guest-local input, real system/application workflows, and stopped appliance acceptance |
| [`009-macos-administrator-sheet-control.md`](009-macos-administrator-sheet-control.md) | complete | Target-resident control of normal macOS administrator sheets with a one-shot non-echoing credential channel and independent effects |
| [`010-macos-full-aqua-software-testing.md`](010-macos-full-aqua-software-testing.md) | complete | Accepted logged-in Tart software-testing control through target-native semantics, visual fallback, privacy prompts, system dialogs, and administration with outer UI prohibited; image omissions recorded |
| [`011-macos-java-electron-framework-coverage.md`](011-macos-java-electron-framework-coverage.md) | complete | Closed the prepared Tart image's Java and Electron omissions with pinned runtimes and four-framework target-native acceptance |
| [`012-linux-gnome-wayland-resident-control.md`](012-linux-gnome-wayland-resident-control.md) | complete | Accepted guarded Ubuntu GNOME Wayland resident semantics, capture, input, system surfaces, provider composition, and reboot recovery |
| [`013-unified-desktop-entry-and-conformance.md`](013-unified-desktop-entry-and-conformance.md) | active | Common target lifecycle/readiness and resident-control client with explicit platform escape hatches and three-desktop conformance |
