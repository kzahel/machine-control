# 098 — Windows browser file uploads

Status: completed source implementation and focused x64 candidate acceptance.
Signed release and broader platform qualification remain separate.
Owning topics: [browser control](../../topics/browser-control.md) and
[Windows desktop](../../topics/windows-desktop.md).

## Objective and completion conditions

Add the shared extension's direct file attachment operation to the Windows
desktop product. Accept `browser.upload` through the existing CLI/SDK vocabulary,
browser grants and live ownership. Prove a direct file input and a button whose
chooser is intercepted, with an independent server checking received filenames,
byte lengths and SHA-256 hashes. Commit after required checks pass.

## Boundaries

Reuse `chrome.debugger` and CDP; do not script OS file dialogs or introduce a
privileged helper. Paths name files on the browser's target machine. Validate
all paths before forwarding any. Keep request acceptance and CDP attachment
delivery separate from the website's independently observed upload effect.
Use a claimed VM and a separately identified Chrome for Testing browser.
Preserve browser registration, installed products, initial power state and
credentials; keep all concrete staging and evidence private. Signed release,
ARM64 live and physical execution remain distinct qualification gates.

## Ordered work

### 1 — route and validate attachments

Add the typed file list, advertise upload as a browser mutation and retain
grant, owner, prompt, Pause/Stop and reference-generation fences. Validate
bounded readable regular files on local drive-qualified paths. Refuse UNC,
device and alternate-stream paths, hidden/private storage and reparse links.
Explain local-file attachment in Windows browser consent UI.

### 2 — prove the real extension and independent upload effect

Use the actual operator UI and a browser-only owner. Exercise single/multiple
files, spaces and Unicode names, direct inputs and intercepted buttons. Refuse
invalid batches, stale references and unsupported chooser selections without
another server effect. Confirm Pause and Stop. Restore owned registration and
reap all test processes.

### 3 — validate and record the completed slice

Run Windows format/contracts, x64/ARM64 self-contained publishes, frontend/native
shell checks and the focused live runner. Update the provider/platform corpus,
current topics and operator guide with actual evidence and limitations.

## Validation and result

**Current — conformance-tested for the staged x64 desktop route:** all 23
checks pass in a claimed Windows-hosted VirtualBox VM with the actual desktop
operator UI and Chrome for Testing 154.0.8037.92. A browser-only live SDK owner
uses the common CLI upload request parser. Direct two-file attachment and
intercepted single-file selection produce exact independently received byte
lengths, SHA-256 hashes and space/Unicode filenames on the loopback HTTP server.
The provider route is `chrome.extension/cdp`; no OS-dialog input or UAC helper
is involved. Attachment acknowledgement reports confirmed delivery with an
unverifiable application effect, while the fixture independently proves upload.

Off-state and unowned dispatch, invalid/missing/directory/UNC/stream paths,
mixed valid/private batches, browser-versus-DevTools authority, superseded
references, single-picker multi-file refusal and buttons without a chooser
pass. Pause interrupts the owner, resumed ownership rejects its old reference,
and Stop leaves the independent upload count unchanged. A button without a
chooser completes with the existing bounded provider timeout; uncertain results
are not replayed. Native contract coverage additionally checks file count,
AppData/dot directories, hidden files, locked files and request serialization.
The local file-symlink test reports an OS privilege skip rather than a pass.

Validation passes: runtime and desktop-contract format verification, desktop/
unlock contracts, self-contained x64/ARM64 publishes, eight extension lifecycle
checks, all 231 common-client tests (nine platform skips), TypeScript/Vite and
the native Tauri debug build. The accepted runtime
SHA-256 is
`60866b8f83c06124d6ce66d29f77c3df46b903da8c3e68b684daf4b6ec552384`.
This is an unsigned development working-tree assembly, not signed installed
release evidence. ARM64 live, physical hardware, other browsers, full installed
CLI/package replacement and hostile same-user containment are not established.
Chrome reopens validated paths; concurrent local file replacement remains a
documented limitation.

The repeatable runner is
[`browser-upload-live.py`](../../tests/windows/browser-upload-live.py), with
staging and cleanup requirements in the [Windows test guide](../../tests/windows/README.md#browser-upload-acceptance).
It restores native messaging registration, stops access, closes ownership,
reaps its app/browser and stops the fixture server. Concrete payloads, profile,
HTTP evidence and VM identity remain private. Independent controller inspection
confirms no owned processes, candidate registration, staging directory or
scheduled task remains. Canonical credential verification passes. The VM
returns to its original powered-off state in approximately 40 seconds using
the existing configured shutdown scheduling assist; no forced power cut is
used. The exact target claim is released. This does not establish unassisted
VirtualBox lifecycle reliability.

Testbed friction: cold boot reached a frozen sign-in surface with stalled SSH.
One exact claimed pause/resume recovery restored administration, followed by
canonical stored-credential login without console input. Broad recursive browser
discovery was stopped and replaced by bounded directory inspection; no separate
test browser was present, so a disposable Chrome for Testing copy was staged.
The initial runner preflight treated PowerShell's absent-process exit status as
failure; the explicit count fixes that fixture issue. The subsequent full run
passes without product changes or effect retries.
