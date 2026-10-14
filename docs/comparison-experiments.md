# Run route-comparison experiments in a macOS VM

Status: **Current, bounded live-tested** for guest YA/Codex through AAR,
Computer Use, MC CLI and the experimental JS route in disposable Tart guests.
Five workflows have initial evidence; [Tactical 124](tactical/124-native-behavior-and-efficiency.md)
adds a five-repeat TextEdit pilot and measurement hardening. Explicit model
settings, Claude collection, menu/recovery scenarios and instruction comparisons
form the next [baseline gate](tactical/125-agent-capability-baseline.md). Both
profiles have now completed arithmetic qualification; seven-scenario GUI smoke
and repeated coverage remain pending.

Purpose: run many paired trials of the same UI task, one driven through
Machine Control and one through Codex Computer Use, inside disposable macOS
guests. A host-side analyst agent then compares transcripts, oracle results
and usage notes to find where Machine Control falls short. The first manual
comparison is recorded in [Tactical 118](tactical/118-usage-friction-journal.md).

## Shape

```text
Controller host (Apple Silicon Mac)
  agent-auth-router (AAR)        loopback only; one revocable client token
                                 dedicated to experiment guests
  YepAnywhere (host)             analyst sessions over collected results
  trial driver                   claims workspaces, opens tunnels, runs trials
  machine-control CLI            --target macos lifecycle and workspaces
        │  one SSH connection per trial guest
        │    -R guest 127.0.0.1:8417 → host AAR 127.0.0.1:8417
        │    -L host 127.0.0.1:PORT  → guest YA 127.0.0.1:3400
        ▼
Trial guest (isolated APFS clone of a sealed experiment base)
  Machine Control resident        appliance policy: standing grant
  machine-control checkout + CLI  agents use --target host (target-native)
  YepAnywhere (guest, loopback)   launches the trial's Codex session
  Codex CLI                       model traffic through the tunnelled AAR
  ChatGPT app + Computer Use      the comparison route
  Chrome + Machine Control ext.   browser route for Machine Control
  task fixtures and oracles
```

Design choices:

- **Trials run inside the guest.** Both routes are then target-native, the
  same placement as an agent on a person's Mac. A host agent driving the
  guest would measure a different (outer or remote) route.
- **One clone per trial.** The clone is discarded on release, so tasks need
  no cleanup and earlier trials cannot leak state into later ones. The
  oracle reads the end state before release.
- **AAR stays on loopback.** AAR refuses non-loopback binds, and YA's AAR
  pool integration uses a local socket that cannot reach another machine.
  An SSH reverse forward makes the host gateway appear on the guest's own
  loopback, so guest clients use the same `http://127.0.0.1:8417` URLs as
  host clients, with a dedicated, revocable gateway client token.
- **Guest YA stays on loopback.** The host reaches it through the trial's
  SSH local forward, so the guest server needs no password, LAN bind or
  exposed port.
- **Results are pulled, not shared.** The driver copies transcripts, notes
  and oracle output to a private results directory on the host. Host YA
  analyzes that directory; it does not need a multi-host session view.

## 0 — Qualify a fresh experiment base

These checks established the current Codex base in Tactical 119. Repeat them
for a fresh base/provider configuration; Tactical 125 adds explicit model,
effort, speed and usage qualification before new comparison batches.

1. **Computer Use through AAR.** On the host, start a YA Codex session whose
   Codex configuration uses the AAR provider and ask it to run
   `cua.getState()`. The earlier Computer Use runs used a direct ChatGPT
   login (`model_provider: openai`); the later guest trials proved AAR for the
   pinned base. If qualification of a new base fails, guest
   Codex needs its own ChatGPT login for the Computer Use arm.
2. **Computer Use in a Tart guest.** Install the ChatGPT app and Codex
   Computer Use in a guest, grant Accessibility and Screen Recording, and run
   one `cua.getApp("Finder")`. Note any sign-in or entitlement prompt.
3. **Token reaches guest agents.** In a guest YA Codex session, confirm the
   gateway token variable is visible to Codex (print only whether it is set)
   and that a turn completes through the tunnel.
4. **Clones keep grants.** Boot an isolated workspace clone of the base and
   confirm Machine Control `target doctor` (standing grant, capture, input)
   and Computer Use both work without new consent prompts or a login screen.
5. **Guest YA through the tunnel.** From the host, create a session with
   `POST /api/projects/PROJECT_ID/sessions` against the forwarded port and
   poll it to completion.

## 1 — Build the experiment base (once per macOS release)

Follow the [Mac VM bootstrap](../platforms/macos/docs/bootstrap.md) for a
prepared image and record a [provisioning journal](provisioning-journals.md)
throughout. Size the disk before first boot; the default is too small for
developer tools plus apps.

1. Clone the prepared image to a new private candidate, set its disk size,
   pin it in private inventory, and bring it up under a claim.
2. `bin/machine-control --target macos testbed -- deploy-ui` installs the
   resident with the root-owned `appliance` policy, a standing grant
   appropriate for a dedicated test VM. Grant Accessibility (`authorize-ui`)
   and Screen Recording as the bootstrap guide describes.
3. Establish the guest login credential in the controller secret store and
   confirm the desktop session returns after reboot without manual login.
   **Open:** whether the prepared image already signs in automatically.
4. Install developer tools, Node 24, a machine-control checkout at the same
   relative path agents expect (`~/code/machine-control`), the YepAnywhere
   CLI and the Codex CLI.
5. Run guest YA as a per-user LaunchAgent bound to `127.0.0.1:3400`.
6. Install the ChatGPT app and Codex Computer Use; grant their permissions.
7. Install Chrome and the Machine Control extension; confirm `browser tabs`.
   Chrome for Testing accepts `--load-extension`; branded Chrome does not.
8. Create one AAR gateway client for experiment guests on the host. Keep its
   token in the controller's private secret store and copy it to a mode-0600
   file in the guest through SSH standard input, never through arguments.
   Point guest Codex (and Claude, if used) at `http://127.0.0.1:8417` using
   the AAR client configuration. Revoking the client cuts off every guest.
9. Install task fixtures and oracle scripts.
10. Run the checks from step 0 on the base, stop it, prove it as the
    workspace ready base, and finish the provisioning journal.

Raise the private workspace limits only as far as disk and memory allow.
macOS permits at most two macOS guests running at once on one host, so plan
for two concurrent trials.

## 2 — Write tasks

A task is a directory with a route-neutral prompt, a guest setup step, an
oracle and a timeout. Keep generic tasks public; keep results private.

```text
tasks/load-unpacked-extension/
  task.json        id, timeout, repetitions, required apps
  prompt.md        what to do; no route instructions
  setup.sh         runs in the guest before the agent starts
  oracle.py        runs in the guest afterwards; prints pass/fail JSON
```

The driver appends exactly one route line to the prompt:

- *Machine Control:* use Machine Control (`--target host`, see the macOS host
  skill) for UI control; no Computer Use, AppleScript or file edits.
- *Computer Use:* use Codex Computer Use for UI control; no Machine Control,
  AppleScript or file edits.

Both add: nobody is at the computer; if blocked, stop and report.

Oracles check the application's own state (preferences, files, databases)
rather than the agent's claim. Start with tasks that exercise known weak
spots: native Open and Save panels, `chrome://` pages, System Settings
toggles, Finder drag and rename, permission prompts, and menus.

## 3 — Run a trial

For each task × route × repetition, the driver:

1. acquires an `isolated` workspace for `macos` with a claim attributed to
   the experiment run, and waits for `target doctor`;
2. opens the SSH connection with both forwards;
3. runs `setup.sh` in the guest;
4. creates the guest YA Codex session with the composed prompt, in bypass
   permission mode, and polls until it is idle;
5. runs `oracle.py`;
6. collects the guest Codex transcript, `usage show --commands` JSON, guest
   `audit history`, the oracle result and a final capture into
   `RESULTS/RUN/TASK/ROUTE-N/`;
7. closes the tunnel and releases the workspace, discarding the clone.

Randomize route order across repetitions. Record per trial: oracle pass,
wall time, tool calls, Machine Control refusals by error code, fallbacks
attempted, usage notes written, and whether the agent asked for a person.

## 4 — Analyze on the host

Start a host YA session in the results directory per batch:

> Compare Machine Control and Computer Use trials in this run. For each task,
> report pass rates, time, and where the Machine Control transcripts spent
> effort or failed while Computer Use did not, and vice versa. Classify each
> Machine Control gap as missing typed operation, grammar or help,
> semantics or accessibility coverage, verification cost, or agent error.
> Propose the smallest fix for each, citing trial paths.

Promote only sanitized conclusions into topics and tacticals. Transcripts,
captures and session IDs stay in the private results directory.

## Safety

Guests are dedicated test appliances. Do not sign in to personal accounts in
a guest beyond what the Computer Use arm proves it needs, and record that
decision. The AAR client token is the only model credential in a guest;
revoke it when a run ends or a guest image is retired. Experiments never use
the controller's own desktop.

## Reproducible measurement (Tactical 124)

The runner now freezes the controller HEAD into a Git bundle and checks out
that exact commit in every disposable guest. Commit experiment edits first.
`--seed` records repeatable route order, and `manifest.json` records the commit,
fixture hashes and full plan. The installed resident and Computer Use binaries
remain the base image's; record their hashes separately before attributing a
cross-batch change to client code. Model configuration must likewise be fixed
in the base; transcript model context records disclose what actually ran.

`--credential-file` names the canonical controller-local base login secret.
The runner requires a regular mode-0600 file and preserves its inherited value
in a separate private workspace secret file. Contents never enter command
arguments or result records. Each trial starts and closes a provisioning
journal. Direct SSH, YA and oracle steps remain explicitly outside automatic
command audit coverage.

`agentSeconds` spans the first task start to final completion, including waits
between recovered provider turns; it never comes from polling. Codex
`activeTurnSeconds` separately sums provider-reported turn durations, while
`betweenTurnSeconds` exposes gaps and `providerErrors` records capacity/errors.
`controllerWaitSeconds` retains polling separately. A final unresolved provider
error makes a trial unqualified even if a partial application effect occurred. Missing process state waits until the deadline;
missing completion, malformed transcripts and timeouts invalidate the trial.
Timeout cancellation is verified before reading an oracle. An unresolved
workspace release stops the batch.

`toolCallsByName`, serialized `toolOutputBytes`, paired tool round-trip intervals,
explicit transcript image items and cumulative token usage expose different
costs. Intervals may overlap; output bytes are not token counts; explicit image
items are not a screenshot count. Native operation counts remain unavailable
without instrumentation. The direct-socket JS prototype is explicitly labeled
as skipping claims and controller audit. Do not call its difference a measured
benefit of persistence alone.

Offline checks: `python3 -m unittest discover -s tests/experiments -p 'test_*.py'`.

`report_batch.py RESULTS/RUN` summarizes valid successful trials by task/route,
with failures, timeouts, missing trials and cleanup failures separately. It
never treats a partial batch or duplicate records as complete. Review actual
tool calls before attributing results to a route: the route restriction is a
prompt, not a tool-isolation boundary. The legacy `wallSeconds` diagnostic
excludes workspace acquisition and final cleanup; use transcript `agentSeconds`
for the agent comparison, not that field as an end-to-end provisioning cost.

`successfulTokenUsage` and `allRecordedTokenUsage` report input, cache-read,
non-cached input, cache-write, output, reasoning and total-token distributions
where available. Each metric's `n` is its coverage, not automatically all trials.
The all-recorded view retains failed/invalid-attempt usage. Input includes cache
classes; output includes reasoning. Do not add those breakdowns a second time.
The legacy `successfulInputTokens` field is raw provider input; use the normalized
fields for future cross-provider comparisons. The Claude collector deduplicates native API-message usage and follows YA
session-ID remapping. Missing usage stays unknown; token counts are not subscription cost.

Use `review_trial.py RESULTS/RUN/TASK/ROUTE-N` to inspect deduplicated model tool
calls, alongside the original results and captures. After inspection, record a
private, transcript-hash-bound annotation with `--record --adherence conforming`
(or `violated` / `uncertain`), `--first-ui-call N`, `--discovery-calls 1,2` and
`--notes TEXT`. The first UI call is the first target UI observation or action;
doctor, help and claims are setup. Do not infer native operation counts from a
batched model call. Existing annotations are never silently overwritten.

Reports distinguish oracle/profile passes from `routeVerifiedPasses`, and expose
unreviewed or uncertain traces explicitly. The discovery annotation also keeps
the last available usage checkpoint before the first UI call. That checkpoint
is not exact token attribution: provider usage can arrive later, and a model
call can mix discovery and useful UI work. Use complete task tokens for the
primary instruction comparison; this prefix measurement explains overhead.
