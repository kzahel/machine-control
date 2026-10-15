# Agent capability comparison

Date: 2026-10-15.

**Current, bounded live evidence.** Seven macOS workflows, three qualified repetitions per model/route/scenario cell, in serial disposable Tart guests. Guest YA launched the exact models through AAR at medium effort and normal speed. The current-guide instruction arm was fixed; the CLI quickstart/discovery arms were not compared.

[Tactical 125](../tactical/125-agent-capability-baseline.md) owns the execution record. The [Python session guide](../agent-session.md) describes the source interface. [Aggregate JSON](agent-capability-comparison-2026-10.json) contains full normalized token breakdowns, coverage, failure-separated resources, discovery annotations and source pins. Raw evidence remains private.

## Whole-corpus observations

These are medians over successful tasks in this seven-scenario corpus, not a universal speed ranking. Each profile has 21 qualified trials; successful coverage is the numerator below. Time includes model/tool activity and recovered provider delays, including Python owner admission. It excludes appliance provisioning/disposal. Tool calls are model calls, which can contain several native operations.

Tokens are input plus output, in thousands (k), including cache input and any reasoning already included in output. Do not add breakdowns again. Tokenizers differ; these are not prices.

| Model | Interface | Effect passes | Median seconds | Median tool calls | Median tokens (k) |
| --- | --- | ---: | ---: | ---: | ---: |
| Sol 6.1 | Computer Use | 20/21 | 37.7 | 6.0 | 168.1 |
| Sol 6.1 | CLI | 21/21 | 77.7 | 12 | 376.9 |
| Sol 6.1 | JS prototype | 20/21 | 50.1 | 7.0 | 161.7 |
| Sol 6.1 | Python MCP | 21/21 | 65.1 | 8 | 209.9 |
| Opus 5.5 | CLI | 21/21 | 65.2 | 17 | 865.3 |
| Opus 5.5 | JS prototype | 21/21 | 35.5 | 7 | 336.9 |
| Opus 5.5 | Python MCP | 21/21 | 48.1 | 8 | 418.9 |

Relative to CLI whole-corpus medians, Python reduced time by 16% for Sol and
26% for Opus, calls by 33% and 53%, and reported tokens by 44% and 52%.
These are ratios of medians, not paired-trial causal estimates. Python's
per-scenario median time was higher for Sol on Finder (90.6 vs 86.5 seconds),
menus (133.7 vs 98.4), save (65.4 vs 48.6) and window recovery (65.1 vs 62.9).
Opus was slower on Finder (75.9 vs 66.9) and window recovery (47.7 vs 43.0).
Claims, admission, audit and reference fencing remain part of the Python result.

An effect pass is not clean-workflow certification. Both successful Computer Use extension trials violated the delivered action-time confirmation requirement. All three Sol/JS window trials clicked a different element than the displayed number identified, then recovered. One Opus/JS menu trial temporarily replaced its source and restored it through native version history before passing. All assigned-route reviews conform; that judgment does not erase these separate problems. Other unreviewed confirmation-policy fields remain unknown.

## All-attempt accounting

The following means divide every recorded attempt’s resources by final-effect successes, retaining failed and invalid spend. They are not successful-task medians. Accounting covers these comparison campaigns only; preliminary smokes, earlier candidate revisions and native qualification are separate development evidence.

| Model | Interface | Success / failed / invalid attempts | Seconds per effect pass | Calls per effect pass | Tokens per effect pass (k) |
| --- | --- | ---: | ---: | ---: | ---: |
| Sol 6.1 | Computer Use | 20 / 1 / 0 | 42.5 | 8.1 | 222.3 |
| Sol 6.1 | CLI | 21 / 0 / 0 | 80.0 | 13.0 | 454.9 |
| Sol 6.1 | JS prototype | 20 / 1 / 1 | 54.7 | 8.3 | 192.8 |
| Sol 6.1 | Python MCP | 21 / 0 / 0 | 69.3 | 9.4 | 257.8 |
| Opus 5.5 | CLI | 21 / 0 / 0 | 74.8 | 16.0 | 858.5 |
| Opus 5.5 | JS prototype | 21 / 0 / 0 | 43.7 | 8.8 | 431.9 |
| Opus 5.5 | Python MCP | 21 / 0 / 0 | 52.7 | 8.4 | 448.9 |

The two qualified failures were an unattended Computer Use extension confirmation refusal and a Sol/JS TextEdit tool-discovery failure. The extra invalid attempt came from an extension oracle that read registration before asynchronous persistence completed. Its original receipt and costs remain retained. No qualified failed result was rerun to replace its score.

## Per-scenario distributions

Entries are successful-task median [minimum–maximum]. Effect counts disclose the successful sample size; most rows have three, two rows have two. These ranges are not confidence intervals.

### Sol 6.1

| Scenario | Interface | Effects | Seconds | Tool calls | Tokens (k) |
| --- | --- | ---: | ---: | ---: | ---: |
| Finder rename/move | Computer Use | 3/3 | 19.9 [19.5–50.0] | 5 [5–10] | 134.3 [134.2–270.2] |
| Finder rename/move | CLI | 3/3 | 86.5 [78.3–88.4] | 10 [9–11] | 327.9 [279.5–369.7] |
| Finder rename/move | JS prototype | 3/3 | 58.1 [49.1–59.9] | 7 [7–9] | 162.4 [161.1–205.4] |
| Finder rename/move | Python MCP | 3/3 | 90.6 [79.0–91.9] | 9 [8–12] | 230.0 [202.4–316.9] |
| Unpacked extension | Computer Use | 2/3 | 63.8 [41.5–86.1] | 11.5 [9–14] | 315.0 [245.3–384.7] |
| Unpacked extension | CLI | 3/3 | 69.4 [63.5–85.1] | 13 [12–15] | 402.8 [371.9–531.6] |
| Unpacked extension | JS prototype | 3/3 | 45.6 [32.0–60.1] | 8 [6–9] | 186.2 [139.9–202.2] |
| Unpacked extension | Python MCP | 3/3 | 57.4 [55.6–61.2] | 8 [8–8] | 220.3 [214.9–223.7] |
| Settings scroll bars | Computer Use | 3/3 | 15.9 [15.9–54.3] | 4 [4–4] | 117.7 [114.2–117.7] |
| Settings scroll bars | CLI | 3/3 | 107.0 [85.4–184.3] | 20 [18–24] | 790.9 [693.8–885.5] |
| Settings scroll bars | JS prototype | 3/3 | 20.3 [18.8–32.8] | 4 [4–4] | 99.6 [98.6–104.7] |
| Settings scroll bars | Python MCP | 3/3 | 47.2 [41.5–68.4] | 8 [7–8] | 209.3 [181.7–209.9] |
| TextEdit menus | Computer Use | 3/3 | 53.6 [48.3–74.0] | 15 [12–15] | 424.2 [329.6–424.6] |
| TextEdit menus | CLI | 3/3 | 98.4 [84.0–111.1] | 15 [14–17] | 607.0 [534.5–777.8] |
| TextEdit menus | JS prototype | 3/3 | 76.7 [70.0–121.3] | 16 [15–19] | 371.5 [369.4–483.2] |
| TextEdit menus | Python MCP | 3/3 | 133.7 [77.7–142.0] | 20 [13–22] | 651.0 [360.8–747.7] |
| TextEdit save | Computer Use | 3/3 | 23.7 [22.9–33.9] | 5 [5–6] | 139.2 [139.1–167.7] |
| TextEdit save | CLI | 3/3 | 48.6 [47.2–49.0] | 9 [9–11] | 264.5 [255.5–313.0] |
| TextEdit save | JS prototype | 2/3 | 31.4 [30.1–32.7] | 5.0 [5–5] | 113.2 [113.1–113.2] |
| TextEdit save | Python MCP | 3/3 | 65.4 [51.4–76.5] | 9 [7–10] | 245.8 [170.0–272.4] |
| File upload | Computer Use | 3/3 | 28.4 [24.3–29.2] | 6 [6–6] | 168.1 [168.1–168.2] |
| File upload | CLI | 3/3 | 58.9 [55.8–76.3] | 13 [11–13] | 417.7 [332.3–434.6] |
| File upload | JS prototype | 3/3 | 28.0 [23.6–52.2] | 5 [4–5] | 113.3 [93.8–113.8] |
| File upload | Python MCP | 3/3 | 41.4 [39.2–44.6] | 6 [6–6] | 151.5 [151.4–151.6] |
| Two-window recovery | Computer Use | 3/3 | 64.1 [47.7–71.2] | 9 [8–9] | 228.0 [203.4–232.9] |
| Two-window recovery | CLI | 3/3 | 62.9 [61.3–77.7] | 10 [9–11] | 325.1 [259.7–376.9] |
| Two-window recovery | JS prototype | 3/3 | 54.9 [51.0–79.3] | 8 [8–8] | 163.9 [163.1–165.1] |
| Two-window recovery | Python MCP | 3/3 | 65.1 [57.2–68.2] | 7 [7–8] | 164.7 [161.0–177.8] |

### Opus 5.5

| Scenario | Interface | Effects | Seconds | Tool calls | Tokens (k) |
| --- | --- | ---: | ---: | ---: | ---: |
| Finder rename/move | CLI | 3/3 | 66.9 [60.4–77.7] | 14 [11–16] | 694.2 [555.9–805.7] |
| Finder rename/move | JS prototype | 3/3 | 44.6 [44.3–60.8] | 9 [8–10] | 430.2 [390.8–478.1] |
| Finder rename/move | Python MCP | 3/3 | 75.9 [71.4–77.9] | 10 [8–12] | 541.3 [429.9–589.9] |
| Unpacked extension | CLI | 3/3 | 85.7 [80.9–133.7] | 21 [17–21] | 1,139.9 [865.3–1,301.6] |
| Unpacked extension | JS prototype | 3/3 | 48.9 [46.6–58.7] | 8 [8–10] | 401.2 [353.5–456.3] |
| Unpacked extension | Python MCP | 3/3 | 50.4 [47.3–70.9] | 9 [8–10] | 464.1 [457.9–564.7] |
| Settings scroll bars | CLI | 3/3 | 70.6 [46.2–100.0] | 19 [14–21] | 1,005.6 [746.5–1,136.9] |
| Settings scroll bars | JS prototype | 3/3 | 23.0 [20.4–29.4] | 4 [3–4] | 222.6 [171.6–222.7] |
| Settings scroll bars | Python MCP | 3/3 | 28.5 [26.4–30.2] | 5 [4–5] | 283.3 [234.3–283.6] |
| TextEdit menus | CLI | 3/3 | 122.3 [112.5–143.4] | 21 [19–21] | 1,120.7 [1,010.8–1,134.3] |
| TextEdit menus | JS prototype | 3/3 | 87.6 [63.5–140.7] | 21 [13–29] | 1,092.2 [645.3–1,514.9] |
| TextEdit menus | Python MCP | 3/3 | 70.6 [54.6–113.2] | 15 [9–22] | 731.8 [437.4–1,270.1] |
| TextEdit save | CLI | 3/3 | 47.1 [38.6–48.9] | 11 [11–13] | 549.1 [547.3–651.2] |
| TextEdit save | JS prototype | 3/3 | 35.5 [25.2–43.8] | 7 [6–7] | 294.1 [292.2–336.9] |
| TextEdit save | Python MCP | 3/3 | 45.3 [42.0–50.3] | 8 [7–8] | 418.9 [359.0–425.2] |
| File upload | CLI | 3/3 | 61.4 [60.6–65.2] | 19 [17–20] | 1,023.3 [1,018.6–1,090.4] |
| File upload | JS prototype | 3/3 | 17.1 [15.9–26.8] | 5 [4–5] | 250.1 [209.2–250.3] |
| File upload | Python MCP | 3/3 | 34.8 [34.5–48.1] | 5 [5–5] | 277.4 [277.3–284.2] |
| Two-window recovery | CLI | 3/3 | 43.0 [39.9–65.1] | 10 [8–12] | 514.4 [410.9–705.8] |
| Two-window recovery | JS prototype | 3/3 | 28.4 [25.8–31.4] | 7 [7–9] | 330.9 [323.5–404.1] |
| Two-window recovery | Python MCP | 3/3 | 47.7 [38.2–48.6] | 7 [7–8] | 357.1 [333.6–405.5] |

## Sampled guest interference

Only the two-window fixture measures these counters. Values are median [minimum–maximum] across three reported trials. Sampling is every 20 ms and includes fixture startup; it can miss brief transitions and does not attribute a transition to an individual action. Controller-host focus/cursor behavior was not measured. Zero sampled cursor changes does not prove universal noninterference.

| Model | Interface | Focus transitions | Cursor transitions |
| --- | --- | ---: | ---: |
| Sol 6.1 | Computer Use | 2 [2–3] | 0 [0–0] |
| Sol 6.1 | CLI | 2 [2–3] | 0 [0–0] |
| Sol 6.1 | JS prototype | 2 [2–2] | 1 [1–1] |
| Sol 6.1 | Python MCP | 2 [2–2] | 1 [1–1] |
| Opus 5.5 | CLI | 2 [2–2] | 0 [0–0] |
| Opus 5.5 | JS prototype | 2 [2–2] | 0 [0–0] |
| Opus 5.5 | Python MCP | 2 [2–2] | 0 [0–0] |

## Interpretation boundaries

- Python retains claim renewal, owner admission and per-operation audit. Its first call includes the configured ten-second admission notice. The CLI baseline uses the direct grant path with claims/audit; the JS prototype omits claims/controller audit. These are whole-workflow comparisons, not persistence-only or Python-versus-JavaScript language experiments.
- Python’s Mac provider rotates native references. The client assigns new numbers and refuses old ones rather than retargeting them. Repeated stale-number recoveries remain in the costs. Full refreshed trees and bounded polling are still used; native stable identity and notification-based settling were not implemented by this comparison.
- CLI shallow snapshots repeatedly omitted controls that deeper queries exposed. Empty default-depth trees do not establish native accessibility incapability. Command grammar, shell-wrapper assumptions, response-shape handling and tool discovery also contributed measurable work.
- Final oracles check application effects. They do not certify every intermediate action or uninterrupted source preservation. Route restrictions were prompt-based and separately reviewed; a passing model completion message was never the oracle.
- Both exact model profiles were qualified from guest runtime/native transcript evidence. Codex normal-tier selection is attested by YA’s effective process configuration, not an upstream billing record. Medium effort is not an equal compute budget across providers. Computer Use on Claude was not a supported cell.
- Baseline and candidate rounds alternated serially with seeded within-round order. This small corpus and fixed placement do not establish population reliability, remote-facade acceptance, platform generalization or an instruction-arm winner.
- The original Python revision’s 13/14 smoke remains development evidence. The revised candidate’s smoke is the first repetition of the reported candidate campaign, not an extra independent replication.

All recorded comparison attempts have hash-bound assigned-route reviews, reported token usage and confirmed guest disposal. The candidate’s session closure was checked in its audit records. The client tree passed 285 offline tests; the experiment harness/report suite passed 52; strict type checking passed for all three session modules. Native activation/capture qualification is separate from the seven agent workflows.

## Source provenance

Own-repository pins are retained below. Exact third-party binary/runtime hashes and deployment provenance stay private; receipt/report reanalysis checks bind the retained inputs. Evaluator-only continuations did not change task prompts or client behavior.

| Component | Revision or hash |
| --- | --- |
| baselineClient | `52487595f5ebf6cd7b92bbe50397b754d0d53df5` |
| baselineCollection | `715218a7a1125301a429f7c3a1649d419990b15a` |
| pythonClient | `b76d643543ef1bd943802756b98580daaa12470b` |
| pythonCollection | `7c43989fd957504e74df4d5d057f8bb0202bfb8b` |
| reportCode | `b72ea99` |
| driverSha256 | `dd2ee09a7a737c2cff9d84214606214a515fa15c7b0df43763fd5f4d23e54c04` |
