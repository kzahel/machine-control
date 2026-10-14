# Run route-comparison experiments in a macOS VM

Status: **Proposal** with explicit open checks; the experiment base and the
Machine Control route are proven (see Tactical 119). The usage journal, session
attribution, Tart workspaces and target-native `--target host` control are
**Current**. Running Codex Computer Use and YepAnywhere inside a Tart guest,
routing guest agents through the host's agent-auth-router, and the trial
driver are not yet proven; [Tactical 119](tactical/119-vm-comparison-experiments.md)
tracks that build-out.

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

## 0 — Prove the open checks first

Each check is cheap and decides the design. Record outcomes in Tactical 119.

1. **Computer Use through AAR.** On the host, start a YA Codex session whose
   Codex configuration uses the AAR provider and ask it to run
   `cua.getState()`. The earlier Computer Use runs used a direct ChatGPT
   login (`model_provider: openai`), so this is unproven. If it fails, guest
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
