# Native caller authentication experiment

This standalone experiment tests macOS socket peer authentication. It never
contacts the MC resident, grants access, starts YA Desktop, opens a window,
requests TCC permissions or performs desktop operations. It runs the installed
YA bundle's Bun only with an owned socket-client fixture. No installed file
is changed.

```sh
python3 tests/macos/caller-authorization/run.py --app /path/to/YepAnywhere.app
```

This default needs Swift command-line tools and a valid signed YA bundle.
It uses an ad-hoc native fixture with an exact code-hash requirement. That
proves OS identity mechanics, not publisher authentication of the fixture.

To prove the publisher-signed native fixture too, explicitly opt into signing
temporary test executables with the single matching Developer ID Application
identity already available in the local keychain:

```sh
python3 tests/macos/caller-authorization/run.py \
  --app /path/to/YepAnywhere.app --sign-with-app-publisher
```

The runner does not create/import identities, export keys, change keychain
policy, notarize or distribute fixtures. It fails if a matching identity is
absent or ambiguous. Temporary signatures have no timestamp and are only local
test evidence, not release artifacts. Temporary files/sockets and owned child
processes are cleaned up even when a case fails. Signing details and requirement
strings stay transient; output contains only minimized outcomes and artifact
hashes. Each case has a bounded timeout.

The gate reads `LOCAL_PEERTOKEN`, checks its size, resolves dynamic code with
`kSecGuestAttributeAudit`, and checks strict validity plus a supplied requirement
before reading any request bytes. Only the test controller supplies that
requirement. Production trust policy must not come from the connecting client.

The cases cover exact native identity, a renamed copy, a different identifier,
ordinary Python, Bun with forged session metadata, Bun against the real Desktop
executable's requirement, publisher-only trust, and malformed policy. Developer
ID mode also rejects an ad-hoc executable claiming the expected identifier.

The publisher-only case intentionally demonstrates an unsafe candidate policy:
if the bundled interpreter shares the desktop publisher, an unrelated script
is admitted. Conversely, a native executable with the expected signature can
still be launched/copied by an unrelated process. The positive fixture is
launched by this Python runner, not YA. Neither check alone proves session
origin. A real broker must constrain its entry points and delegation channel.

This test is outside the production resident. It does not implement grants,
replay protection, revocation, peer lifetime revalidation or YA integration.
It makes no claim about hostile same-user containment. See
[Tactical 071](../../../docs/tactical/071-desktop-caller-authorization.md) for
results and remaining acceptance gates.
