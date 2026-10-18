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
dispatch, general personal-app control, contacts or camera is implemented.
Selected photos/documents use the separate read-only data plane below.

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

## Independent photo and document reads

The fixture's **Photo and document access** screen opens Android's actual photo
picker and SAF folder picker. It retains one selected photo and one selected
tree, with persistable **read** grants only. There is no broad gallery/storage
permission. The operator separately arms a normal foreground `DataService` for
15 minutes; accessibility enablement and the UI service are unnecessary.

```text
one Python namespace per conversation: phone.photos(), phone.roots(), ...
  -> token-authenticated phone-local data connection per interpreter
    -> shared DataService with independent readers, no exclusive UI owner
      -> ContentResolver / DocumentsContract / Android URI grants
```

`data_client.py` adds `phone` to the same unchanged MC interpreter core:

```python
photos = phone.photos()                  # selected items, not the gallery
roots = phone.roots()                    # selected SAF trees
children = phone.list(roots[0]['id'])     # items + truncation status
photo_id = photos[0]['id']
phone.thumbnail(photo_id)                # actual inline PNG tool result
phone.export(photo_id, 'selected.png')   # new Linux file, refuses overwrite
raw = phone.read(photo_id)               # Python bytes
```

Register `session.py --plane data --receipt PRIVATE_DATA_GRANT` for this tool
description. Initialization/tool discovery opens no native connection and needs
no receipt yet. First execution lazily opens one; separate conversations retain
separate interpreters/connections. Closing one reader does not revoke another.
There is no per-conversation permission editor or production YA registration.

Opaque handles come only from native listings, not caller URIs or filesystem
paths. The native boundary supports no mutations; listings stop at 100 entries,
handles at 1,024, and each read at 4 MiB. Exports create copies in the Linux
workspace, not a FUSE mount or automatic shared filesystem. Revoking Android's
persisted grant prevents subsequent native reads, but cannot erase bytes already
exported to an agent workspace. That workspace needs its own retention policy.

Selection identity survives native app restart and remains visible when revoked.
The service rechecks the persisted permission before and after access. A newly
armed service has a fresh token, runtime generation and handle registry; persisted
selection does not restore runtime authority. **Revoke** releases the actual
persisted URI permission while keeping the selected identity for repair;
**Forget** also removes selection metadata. **Stop** closes every data connection
and deletes its receipt without discarding selections.

Four bounded reader workers admit independent connections; this is not unlimited
concurrency. Provider calls receive cancellation after five seconds, and sockets
expire after 60 idle seconds. An Android provider that ignores cancellation or
blocks a descriptor read is still a gap: cancellation is not hard process
containment. Cloud providers, unavailable/offline media, streaming large images,
writes, multiple selections, reboot/Doze endurance and product lifecycle/audit
integration remain unqualified. Persisted URI identity does not prove an item is
currently downloadable. The special-use foreground-service declaration is a
debug-spike choice, not evidence of store-policy acceptance.

The source study and JSTorrent revision are recorded in
[Android research](../../../research/platforms/android.md#selected-media-and-saf-reference-study-2026-10-18).
No JSTorrent source or storage engine was copied.

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
# Independent photo/SAF test; accessibility stays unchanged:
python3 platforms/android/resident-spike/data_live.py --serial "$ANDROID_TEST_SERIAL" --replace-spike
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

UI restart, remote, unplugged, background/Doze, stable-ID/diff efficiency and
broader personal-app acceptance remain open. This spike is not yet registered
automatically in YA sessions.

**Photo/SAF data plane, 2026-10-18:** the physical Pixel 7a passed real system
photo-picker consent for a unique synthetic PNG and DocumentsUI consent for a
dedicated Downloads child folder. Python ran under the YA app's ordinary kernel
UID, separate from the fixture that held the Android permissions. With the
fixture UI offscreen, two independent persistent interpreters concurrently read
the selected image and document, retained isolated variables, exported original
bytes, and returned an actual inline PNG thumbnail. Controller-side reads of
both Linux exports matched the original fixtures byte-for-byte. Closing one
reader preserved the other; arbitrary URI handles, writes and export overwrites
were refused.

After native app force-stop/restart and explicit re-arming, both persisted grants
still read correctly with new runtime token/generation. On a live connection,
folder revocation refused document reads while photo reads continued, then photo
revocation refused those reads too. Revoked selections remained visible as
unavailable. Stop closed the reader, refused the old receipt and removed the
native receipt file. The harness removed owned media/documents, actual persisted
grants, selection metadata and Linux workspaces; it preserved accessibility
settings throughout. This is app-process restart acceptance, not a reboot,
Doze, cloud-provider or unplugged test. ADB handled setup, real picker actions
and independent witnesses; native data operations used only phone localhost.

The data change also adds a tool-discovery regression: data MCP initialization
and discovery work without any grant file or service. All six spike tests,
49 unchanged MC session tests and ten Android adapter tests pass; native build
and lint are clean. The new data helpers have not yet been exercised by real
model inference or integrated into YA's production permission/onboarding UI.
