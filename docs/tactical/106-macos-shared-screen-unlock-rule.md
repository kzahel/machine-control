# macOS shared screen-unlock rule

Status: source and static validation complete. Signed installation beside
another authorization plug-in, and its live lock/unlock acceptance, remain
open.
Owning topic: [macOS locked use](../../topics/macos-locked-use.md).

## Objective and completion conditions

Native helper setup on a physical Mac failed with only `helper_setup_failed`.
Codex Computer Use had already joined `system.login.screensaver`:

```text
class = rule, k-of-n = 1
rule  = [ com.openai.sky.CUAService.AuthorizationPlugin.remote, use-login-window-ui ]
```

The installer accepted only the stock `[use-login-window-ui]` rule and
refused with `unlock_policy_conflict`. The broker discarded the installer's
output. Removal also restored a saved snapshot, which would delete any entry
another product added after Machine Control.

Completion requires the specific refusal code to reach Permissions, and
setup, disable, removal and health checks that change or check only Machine
Control's own entry in the shared rule.

## Boundaries

macOS replaces whole authorization rights; there is no append or
compare-and-swap. Cooperative writers can still lose an update between one
writer's confirmation and another's write. This slice detects and reports
that drift instead of claiming atomicity. The broker does not repair the rule
on its own; the operator restores it with **Set up**. The dedicated
`org.machine-control.screen-unlock` right, artifact pins, caller
authorization and password fallback are unchanged. **Decision:** the
`org.machine-control.*` identifiers stay for now; a `dev.machinecontrol.*`
rename (matching the project domain) is deferred.

## Ordered work

### 1 — relay helper refusal codes

The broker captures the verified installer's one-line JSON result and relays
a bounded lowercase `errorCode`. Permissions maps known codes, including
policy conflict, contention, untracked installation, management conflict,
invalid bundle and timeout, to operator wording that keeps the code visible.

### 2 — compose the shared rule

`ScreenUnlockRule.h` holds pure composition shared by the Objective-C broker
and the Swift installer (via `-import-objc-header`). A supported rule is
`class = rule` with `use-login-window-ui` and `k-of-n = 1`. A rule with only
the fallback may omit `k-of-n`. Install inserts the entry before the
fallback; removal deletes only that entry; unsupported shapes refuse.
The installer applies each change to a fresh read, writes, confirms and
retries up to five times (`unlock_policy_contended`). The receipt keeps the
original policy as a diagnostic record and no longer pins an installed
snapshot.

### 3 — report drift and peers

Broker health requires the dedicated right and our entry in a supported
rule. An entry removed from an otherwise valid rule reports
`unlock_policy_entry_missing`; Permissions explains that **Set up** restores
it. Status carries `unlockRulePeers`, and Permissions lists those other
entries because each can independently unlock the Mac.

## Validation

- `tests/macos/screen-unlock-rule.m`: composition, ordering, peer
  preservation, refusal of unsupported shapes; added to
  `platforms/macos/tests/smoke.sh --static`.
- A read-only dry run against the physical Mac's real rule produced
  `[codex-entry, org.machine-control.screen-unlock, use-login-window-ui]`
  with `k-of-n = 1`, and removal restored the Codex-only rule.
- `swift test` for the resident (including refusal-message mapping), the
  desktop TypeScript check and Prettier, and ARM64/x86_64 unlock builds.

**Open:** as recalled from Apple's published `authd` source (not
re-reviewed for this slice), a `k-of-n` rule stops early only on
cancellation or internal error, and a deny continues to the next entry.
Codex's entry already precedes the working password fallback, so it denies
cleanly, but a signed install has not yet confirmed that both plug-ins and
the password still unlock.

## Result

**Current:** source and static validation above. **Open:** a signed
candidate installed on a Mac with the Codex plug-in present must show
successful setup, retained Codex entry, covered unlock, password fallback,
removal preserving the Codex entry, and the drift message after an external
removal.
