# Deterministic native efficiency probes

Original AppKit fixture, independent event/state oracle, genuine installed MCP
client, and common-CLI comparison. This is research infrastructure, not a
supported Computer Use integration or a replacement session API.

Run only inside a disposable macOS experiment workspace acquired through the
common CLI. The controller owns doctor, provisioning journal, inherited
credential verification, claim renewal and workspace release. Start a separate
guest-local `host` claim for the MC CLI route and release it before discarding
the workspace. Never run these fixtures on the controller's personal desktop.

1. Copy this directory into the guest. Run `prepare.py --disposable-guest
   --root /private/tmp/native-efficiency-RUN` with a new absolute directory.
2. Resolve the actually installed/enabled Computer Use MCP configuration; pass
   its path as `--config`. Do not choose a cache version by sorting names. The
   host accepts only the Computer Use connector and these two owned app IDs,
   without writing persistent consent. OS consent must already be ready.
3. Run `probe.py --root ROOT --output ROOT/sky --route sky --config CONFIG
   --repetitions 5`, then `--route mc-cli --claim GUEST_CLAIM` with another
   output directory. Do not run providers concurrently against these fixtures.
4. Use `report.py OUTPUT/records.json` for counts, timing and bounded effect
   checks. Keep the raw records private. Collect `provenance.collect(CONFIG)`
   before each campaign; it includes private artifact paths and hashes.
5. Where existing privilege permits it, run `profile.py --root ROOT --output
   ROOT/profile --config CONFIG --pid EXACT_SERVICE_PID`. It compares ten
   unchanged reads and ten press/read sequences, untraced and with API counts,
   syscall counts or sampled stacks; `--workload pointer-and-type` isolates input.
   Probe diagnostics must be clean as well as exit zero. It never changes SIP, entitlements or
   signing. `sudo -n` refusal is a measured instrumentation limit.
6. Reap owned MCP process groups (the clients do this in cleanup), stop the two
   fixture PIDs after verifying their executable paths, retain private results,
   then release the guest claim and controller workspace in finally cleanup.

The fixture reports actual accessibility press callbacks, mouse events, text,
sheet lifecycle and revision changes. A separate sentinel app starts each
background action as foreground/key; its cursor, foreground, local key input
and text are checked independently. Cursor/foreground sampling is 20 ms, so
shorter transient changes can escape observation. Field focus and menu-open
alone have no independent effect verdict; subsequent text/menu-item effects
are checked. Clipboard change count is recorded, but this corpus does not yet
exercise paste/restore.

Trees use 20/100/300 static rows. First-after-resize is not a cold process/cache
measurement. `--section tree --projection compact` isolates MC projection
changes without repeating unrelated cases. External timer updates and action-triggered delayed/burst/continuous
updates are separate cases. Quietness is not proof of application completion.
The MC route includes process, claim and audit overhead; its resident envelope
retains native elapsed time. Sky times include MCP transport/runtime work.
Neither is a pure syscall timing. Repeated reads are intentional experimental
workloads, not recommended agent behavior.

Raw result text, MCP documentation, screenshots, profiling stacks, concrete
process identities and exact third-party artifacts never belong in public Git.
Use the private spike for minimized pins and investigation records and the
public provider dossier for portable conclusions.

## Python capture conformance

After preparing fresh fixture apps, run the source-checkout script
`session_capture.py --root ROOT --disposable-guest --target host` in the guest.
Publish the controlling agent's session ID through the normal environment for
audit attribution. The script acquires and releases its own guest-local claim
through the retained transport. Do not hold another guest-local claim for it.

The test uses captured PNG dimensions and known fixture control bounds, then
checks the fixture's independent mouse callback, revision and scroll-offset
state. It also refuses a reused capture and an independently moved window before
input, and verifies unchanged sentinel content. It does not establish visual
model grounding, interference-free input, or mapping on another provider.
The fixture's private command channel supplies setup and simulated external
movement; it is not part of an agent-task result. Live Mac qualification passed
with a 2× PNG-to-window scale, real pointer callbacks, a changed scroll offset,
and refusal after an external move. This required the shared claim-clock fix
for the guest's older system Python. A separate Sol medium/normal-speed YA turn
also forwarded the inline image and used `Capture.click` on the pointer-only
region; independent down/up callbacks and prompt claim release passed. That
single capability smoke is not a repeated efficiency estimate.
