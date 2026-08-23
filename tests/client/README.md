# Common client tests

Run the dependency-free adapter tests without live targets:

```bash
python3 -m unittest discover -s tests/client -v
```

With an accepted target already running, run the shared guarded workflow:

```bash
tests/client/live-desktop-conformance.sh windows
tests/client/live-desktop-conformance.sh macos
tests/client/live-desktop-conformance.sh linux
```

The live script uses only `bin/machine-control`. Platform cases provide fixture
setup, independent-effect reads, and cleanup through the explicit `testbed` or
`os` escape hatches. The ordinary status, capabilities, local/outside parity,
snapshot, action, capture, and artifact operations all use the common client.
It acquires one two-hour exclusive target-use claim after the read-only doctor,
carries that claim through every operation, and releases it from its cleanup
trap even when conformance fails.
Every run forces the relevant outer-UI prohibition and emits one minimized
`machine-control-common-desktop-conformance/v0` result.

Dependency-free tests also cover native common projections. Android, iOS, and
Quest expose device-shaped `target status`, `target doctor`, and
`target capabilities` without claiming a desktop/resident process. ChromeOS
exposes a desktop-shaped native doctor with current-boot SSH persistence,
profile lock, and an empty common lifecycle set. A lifecycle mutation is
dispatched only when that doctor declares the exact operation.

The fake adapter also covers the explicitly iOS common family: platform
gating, allowlisted request construction, standard-input transport that keeps
fill text out of adapter arguments, strict `machine-control/v0` result
validation, and logical-target/client metadata. Provider-native passthrough
remains behind `testbed --`; Android and Quest do not inherit iOS operations.

The fake VM adapter covers the additive workspace surface on macOS, Linux, and
Windows: strict capabilities, configured and explicit intent, opaque selection
of later adapter calls, normalized mechanisms, typed refusal, private-field
rejection, receipt-bound release, and dry-run-only garbage collection. Shared
provider tests separately exercise private receipt modes/redaction and UTM
persistent, disposable, and policy-gated full-copy behavior.

The same fixtures cover coordinator-neutral target-use claims: policy
discovery, bounded attribution, acquisition/status/renewal/release, global
claim selection, pre-dispatch refusal, and atomic workspace composition.
Shared provider tests add exact-resource contention, fencing, expiry, private
state permissions, adapter enforcement, and claim-checked workspace cleanup.

The same fake adapter proves that `target ensure-ready` is a no-op when ready,
starts an off target only through its declared `up` operation, and refuses to
invent a running-target repair. A reported start failure still receives an
independent final doctor observation without exposing adapter diagnostics.
Candidate tests require a fresh running-ready observation and prove that only
a cleanly stopped second identity assertion is eligible for private promotion.

The maintenance fixtures prove that capability discovery never invokes an
adapter, Windows/macOS/Linux audit and repair use the same common operation
names, and ChromeOS can expose runtime audit/repair while refusing image
certification before dispatch. Reboot remains repair-only and explicit,
certification selects an available exact-source platform composition, and
valid unhealthy JSON preserves a nonzero result. The common projection removes
private boot epochs, endpoints, staging, and platform-only detail.
`ensure-ready` only recommends the read-only audit; it still never performs
maintenance itself.
