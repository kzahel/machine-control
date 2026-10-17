# Android resident bridge spike

Status: experimental, fixture-scoped implementation. Acceptance results belong
below; this is not the installed MC desktop session or a released phone-control
product. Direction: [Android family](../../../topics/android-family-control.md#app-resident-provider-exploration).

## Shape

```text
provider's stdio MCP client
  -> session.py (persistent MC Namespace in existing killable Worker)
    -> existing client/agent_session.py Session/App/image presentation
      -> AndroidTransport (one token-authenticated loopback connection)
        -> Android AccessibilityService (typed native operations only)
```

The Python core is imported unchanged, not copied into a second implementation.
Model-written code executes in the client interpreter, not the accessibility
service. The native service permits only the foreground fixture package and
semantic actions on its input, Apply and Replace controls. Operator settings,
Arm and Stop are not agent actions. No gesture injection, arbitrary shell, ADB
dispatch, personal app access, documents, contacts or camera is implemented.

The operator enables accessibility and arms a 15-minute grant in the fixture.
Its private mode-0600 receipt contains the random loopback port, token and
service generation. Each request checks that grant; one connection owns control.
Stop, expiry, disconnect, service disablement and process loss end ownership.
An idle connection times out after 60 seconds. Authority refusals close the
connection and require explicit reset/re-admission. Stale-reference and
unsupported-operation refusals allow a fresh observation on the same owner;
no operation is replayed.

Snapshots have fresh opaque references, invalidated by new snapshots, actions
and active-window changes. Content events alone do not prove node replacement.
Dispatch refreshes the retained node and checks membership in the current
fixture tree. Identical labels/resource IDs do not establish identity. Stable
Android observation IDs and compact unchanged/diff performance remain unqualified;
the initial implementation deliberately allocates fresh observation numbers.
Window PNG capture requires API 34 and does not enable MC's Mac-specific image
coordinate actions. Delivery is reported separately from an observed task effect.

This is a bounded native grant/ownership experiment, **not desktop claims/audit
parity**. Same-UID shell confinement is not claimed. The fixture service is a
separate app UID from the YA interpreter; the explicitly provisioned grant gives
the interpreter only the service's narrow operation surface. Production caller
authentication, capability grants, audit and generic Android transport integration
remain work. TCP loopback alone is not authorization.

## Build and validate

Use JDK 17, Android SDK 36 and Gradle 8.13 (an existing wrapper is sufficient):

```sh
"$GRADLE_WRAPPER" -p platforms/android/resident-spike :app:assembleDebug :app:lint
python3 -m unittest discover -s platforms/android/resident-spike -p 'test_*.py' -v
python3 -m unittest discover -s tests/client -p 'test_agent_session*.py'
```

The live probe requires an explicitly selected unlocked test handheld and the
debug YA Android host with its Alpine runtime already staged and stopped. It
does not install or reprovision that runtime or touch provider credentials.
The fixture APK and host must have compatible debug signing for instrumentation.

```sh
python3 platforms/android/resident-spike/live.py --serial "$ANDROID_TEST_SERIAL"
# On a subsequent explicit run, replace only this fixture:
python3 platforms/android/resident-spike/live.py --serial "$ANDROID_TEST_SERIAL" --replace-spike
```

ADB installs/launches the fixture through the Android adapter, temporarily adds
only its accessibility service, arms via the native UI, stages a disposable
private workspace, and independently reads the fixture result. The prior
accessibility service list is preserved and restored in `finally`. No radio,
debugging listener, global ADB server or unrelated app configuration is changed.
The debug fixture remains installed but stopped/revoked for review.

`PhonePythonProbe` instrumentation runs a staged Python acceptance script under
the YA app's real UID/SELinux domain, using the already-installed PRoot/Alpine
payload. Its native service runs under a separate fixture UID. Phone-local
control uses localhost directly, with no ADB forward/reverse or ADB command in
that operation path. ADB remains attached for provisioning and independent
observation; this is not an unplugged endurance test.

The script exercises separate interpreter calls retaining variables/app handles,
text and click, actual PNG capture, replacement/stale reference, bad grant and
outside-scope refusal. The controller replaces the input independently while an
old native reference is outstanding, and later taps Stop while ownership is
live. The probe verifies stale refusal, connection closure and rejection of the
revoked grant. It also proves agents cannot press the operator's Arm control.
PRoot reports guest UID 0; the kernel UID witness comes
from `/proc/self/status`, alongside the SELinux domain. Private evidence and a
failure-recovery receipt stay in ignored `.local/`; never commit those files.

For provider registration, stage this script beside an unchanged `client/`
directory and start `python3 session.py --receipt PRIVATE_GRANT_FILE` as a stdio
MCP server. It exposes `mc` and `mc_reset`; every call supplies the provider's
published `session_id` for attribution. That ID is not bearer authority. One
interpreter binds to one such ID. Registration and discovery do not acquire the
native grant; the first code call opens it.

`--session-id-file PRIVATE_FILE` instead uses MC's existing validated session-ID
publication reader, checking the published native provider ID on every tool call.
The real-provider probe publishes that ID from the CLI's own startup event;
it does not invent an ID or assume a late environment variable reaches MCP.

Opt in to real subscription-backed inference with an existing AAR checkout:

```sh
python3 platforms/android/resident-spike/live.py --serial "$ANDROID_TEST_SERIAL" \
  --replace-spike --aar-checkout "$AAR_CHECKOUT"
```

The harness selects an existing enabled enrollment for each provider, creates a
temporary scoped gateway grant, and uses an owned ADB reverse only for inference.
Control still travels directly over phone localhost. It runs Codex and Claude
serially with only the phone MCP tools, captures their real tool events, and
checks each fixture-file result independently before the next provider runs.
The grant is revoked with HTTP 401 verification and only its owned reverse is
removed. A private recovery lease remains on cleanup failure. No upstream OAuth,
normal provider home or YA development configuration is imported or replaced.

## Acceptance

**Live-tested 2026-10-17 on a physical Pixel 7a, Android API 37:** eight separate
Python snippets retained an app handle and variables, entered a fresh challenge,
pressed Apply, observed the result and captured a real window PNG. An independent
ADB read of the fixture's private result file matched the challenge. The native
provider refused a previous input reference after replacement with the same
label/resource ID, an invalid grant and a request targeting another package.
The Python kernel UID and SELinux domain established normal Android app execution
in the YA app, separate from the native fixture app. No ADB command or forwarding
was used for the phone-local operation channel. Cleanup restored accessibility
settings and removed the temporary host workspace.

**Real providers, 2026-10-17:** Codex completed seven MCP calls and Claude six
on the same physical phone, using real subscription inference through temporary
AAR grants. Both retained Python state across calls, entered/applied their own
challenge with an independent controller file witness, returned an actual inline
PNG tool result, and closed ownership. Final tool events contain no failed calls.
The subsequent deterministic run also passed externally triggered same-label
replacement, operator-rearm refusal, live Stop/connection closure and revoked
grant re-admission refusal. Accessibility settings and temporary workspaces were
restored/removed; the inference grant and tunnel were cleaned up.

The earlier real Codex attempt exposed over-broad invalidation on content events
and terminal handling of recoverable stale references. Both are corrected;
removed nodes still fail dispatch membership checks. An initial provider launch
also inherited open stdin; provider subprocesses now explicitly use `/dev/null`.

Build/native lint pass without warnings, as do 49 existing session tests, five
spike transport tests and ten Android adapter tests. Restart, remote, unplugged,
background/Doze, stable-ID/diff efficiency and broader personal-app acceptance
remain open. This spike is not yet registered automatically in YA sessions.
