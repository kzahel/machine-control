# Usage-journal review: recurring control failures

Status: **Current — triaged observations and source checks, not runtime fixes.**
Owning topics: [browser control](../topics/browser-control.md),
[Mac locked use](../topics/macos-locked-use.md),
[Android-family control](../topics/android-family-control.md),
[target readiness](../topics/target-lifecycle-and-readiness.md), and
[operational workflows](../topics/operational-workflow-automation.md).

## Review basis

The review scanned 366 private usage notes dated 2026-10-13 through 2026-11-01,
then read related incident sequences, subsequent outcomes, current topics and
selected implementations. Selected claim/session audit histories were also
inspected. Some audit pages were truncated, and provider escapes are outside
complete coverage. This is not a full transcript reconstruction or a fresh
live regression campaign.

The notes include 177 friction reports and 100 summaries; they are not 366
distinct bugs. Some describe other applications, fixture mistakes, expected
policy refusals, or subsequently repaired defects. Exact note/session/claim
references and the review crosswalk remain in the private usage store.

## Suggested priorities

**Proposal:** prioritize by workflow impact and strength of remaining evidence,
not raw note count. These rows do not establish a shared root cause.

| Priority | Finding | Current evidence and next step |
| --- | --- | --- |
| High | Background browser clicks lack application effects | Reports span several real sites and a corrected owned locked-console fixture. Establish the exact installed provider and compare matched console/tab states; the [click gap](2026-11-01-locked-background-browser-click.md) owns the latest reproduction. |
| High | Covered editing and guardian reliability remain costly on physical Macs | One task needed 125 clean owner sessions to complete and verify nineteen descriptions; uncertain edits could become duplicate text after replay. VM repairs and short physical passes do not close the original intermittent failures. The [covered-control gap](2026-10-29-covered-observations-and-duration.md) owns these distinct symptoms and qualification limits. |
| High | Android UI work lacks common exclusive ownership | Interactive checks observed unrelated foreground changes, suspected another session, and stopped because target claims were unsupported. Current source confirms that limitation; it does not prove who caused the changes. Extend authoritative device ownership before relying on concurrent agents. |
| Medium | VM lifecycle/readiness repeatedly blocks ordinary testing | UTM automation/identity failures, accepted starts with no running guest, delayed boot readiness, long diagnostics, failed saved-state resume and opaque shutdown failures recur. Separate provider, guest and wrapper causes; independently verify effects and bound each phase. The [UTM dossier](../research/providers/utm.md) records mitigation and the unresolved endpoint cause. |
| Medium, confirmed defect | Android doctor crashes when the device is unavailable | The current unavailable-state formatter raises `NameError` offline. Repair and test disconnected/unauthorized/error paths without inventing a boot generation. See the source finding below. |
| Medium | Terminal/frame text delivery is incomplete | Repeated terminal reports show `browser type`/`Input.insertText` acknowledged with no text, while Enter or explicit key events worked. Qualify frame-aware text/key delivery and independent terminal effects; do not infer that ordinary HTML typing fails generally. |
| Medium | Installed capability and guide skew wastes recovery work | Current-source help advertises dialog handling absent from one installed resident; a legacy Windows health route failed while the common resident worked. Discover actual deployed support and give actionable version/route diagnostics rather than assuming source availability equals deployment. |
| Medium | Automated failure notes omit actionable diagnostics | 56 notes contain the identical generic packaged-acceptance failure sentence. Preserve a private run reference, failed phase/check and cleanup outcome so review can separate causes. See the logging finding below. |

### Android unavailable-state doctor

**Current, source-reviewed and reproduced offline:**
[`unavailable_doctor`](../platforms/android/android_device.py) constructs
`extensions.generation` from `status["bootGeneration"]`, but `status` is not
defined in that function or available as a module global. Calling that
formatter directly raises `NameError: name 'status' is not defined` without
contacting any device. The same failure was reported during separate transport
outages more than two weeks apart.

**Proposal:** return a valid minimized unavailable doctor document and represent
unobserved generation explicitly according to the contract. Add direct formatter
coverage plus error-path coverage through doctor dispatch. Do not replace an
unavailable device observation with another selected device or a guessed state.

### Automated failure-note quality

**Current, source-reviewed:**
[`tests/macos/packaged-acceptance.py`](../tests/macos/packaged-acceptance.py)
writes a fixed sentence from its broad exception handler. All 56 matching notes
say to inspect private evidence but name no failed check, phase or evidence
locator. Claim/session audit can help recover context, but omits payloads and
has independent retention/coverage limits. Identical text does not establish
identical causes or duplicated execution.

**Proposal:** keep every failed attempt while attaching a bounded private run
reference, closed failure code/check, phase and cleanup status. Group repeated
observations for review without deleting attempts or exposing raw stderr,
secrets, personal page contents or deployment identities.

## Other findings and exclusions

- Background native menu activation and pointer/text focus interference have
  independent fixture evidence in [Tactical 124](../docs/tactical/124-native-behavior-and-efficiency.md)
  and remain in the [product roadmap](../topics/computer-use-positioning.md).
  Do not merge those native-provider findings into the browser-click cause.
- ChromeOS tray activation failed in one tablet-mode state and passed after a
  physical lid transition, including reclosed-lid acceptance. The existing
  [platform report](../research/platforms/chromeos.md) retains that bounded
  recovery; neither an update regression nor a firmware cause was established.
- Linux greeter/session readiness, secure login availability and normalized
  action parity deserve a separate platform sweep. Old greeter-only and
  unsupported-action notes do not establish current cross-platform breakage.
- macOS keyboard layout/modifier faults, the packaged file-dialog crash,
  Android secret-stdin/helper startup faults, and repeated ChromeOS activation
  prompting have subsequent repair/acceptance records. Keep their exact
  coverage limits rather than reopening them from older notes alone.
- Numeric retargeting and ambiguous application selection were demonstrated
  in the experimental frozen JS comparison, not the supported Python reference
  model. It remains a reason not to promote that prototype unchanged.
- Account reauthentication, expected protected-page scripting refusals,
  exclusive-claim contention, storage-reserve refusals and ordinary stale
  reference rejection are not automatically product bugs.

## Recommended execution order

**Proposal:** fix the deterministic Android doctor defect first as a bounded
repair. In parallel workstreams if later authorized, isolate background
browser effects and qualify the repaired covered-control package on the
intended physical configuration. Device UI ownership is the next substantial
contract gap. Improve failure-note diagnostics before using journal counts to
prioritize another broad acceptance campaign. Keep lifecycle recovery and
capability negotiation as separate implementation slices.
