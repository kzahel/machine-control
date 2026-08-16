# Tactical 024: Quest Wireless ADB

Status: complete.

Topic: `android-family-control`.

## Objective

Add a convenient, temporary, authenticated wireless transport to the physical
Quest adapter without root, published network inventory, arbitrary Android
selection, or a second target identity. Preserve the configured USB identity
as the authority and let ordinary Quest operations use a verified
controller-local endpoint after the cable is removed.

## Completion conditions

- `quest wireless status|enable|disable` exposes typed support, activation,
  verification, and cleanup behavior.
- Enable starts from the exact authorized USB Quest, requires secure ADB and a
  private Wi-Fi address, refuses an active lease, and verifies device identity
  and Quest profile over the network endpoint.
- A mode-`0600` local receipt lets the existing USB selector reconnect the same
  Quest wirelessly while keeping the address and serial out of Git and common
  results.
- Missing, unauthorized, changed-identity, non-Quest, insecure, public-address,
  and active-lease cases fail closed.
- Disable observes endpoint loss, restores USB mode, and clears local state.
- Unit/compile checks and a live exact-device wireless doctor pass.

## Boundaries

- Do not root the headset, weaken RSA authorization, enable a persistent boot
  listener, publish a network address, or make a logical target alias bearer
  authority.
- Do not claim Horizon OS exposes Android's standard QR-pairing UI merely
  because its ADB service reports pairing capability.
- Do not change transport during an active Quest lease or let a transport
  transition strand proximity, settings, package, reverse-port, or sleep
  cleanup.
- Keep classic ADB-over-TCP profile-owned by Quest; the shared provider remains
  neutral transport machinery.

## Implementation steps

### 1 — prove the stock wireless route

Query the authorized Quest's ADB Wi-Fi, QR, secure-authentication, network, and
persistence capabilities without mutation. Enable Android's port 5555 route
over the pinned USB transport, connect from the controller, compare stable
device identity, and run the full Quest doctor through the exact endpoint.

### 2 — bind wireless transport to the USB identity

Add guarded status, enable, and disable commands. Store the endpoint, USB
selector, and independently observed device identity only in a hashed-name,
mode-`0600` controller-local record. When USB is absent, reconnect the receipt
and revalidate authorization, identity, and Quest profile before selection.

### 3 — preserve lease and network safety

Require secure ADB, a private non-link-local `wlan0` address, exact-device
matching, and no active lease. Treat the route as temporary across `adbd` or
headset restart. Make disable observe network endpoint removal before deleting
the receipt.

### 4 — validate and publish current truth

Cover enable, fallback, identity drift, address policy, lease refusal, and
disable with unit tests. Run compile, shared ADB/client regression, diff, and
public-data checks. Prove the common pinned target works with USB removed, then
update the Quest guide, skill, research, and Android-family topic.

## Validation plan

- `cd platforms/quest && python3 -m unittest discover -s tests -v`
- `python3 -m unittest discover -s providers/adb/tests -v`
- `python3 -m unittest discover -s tests/client -v`
- `python3 -m compileall -q platforms/quest providers/adb`
- live `quest wireless enable --json`, exact-endpoint doctor, a common doctor
  through an isolated ADB server with no USB transport, `wireless status`, and
  controller-local file-mode check
- `git diff --check` and public-data review

## Result

Completed 2026-08-16.

The stock Quest 3 reported Android API 34, secure ADB, Wi-Fi and QR-pairing
support, disabled wireless state, and no persistent TCP property. The guarded
enable command selected the private-inventory USB target, required its exact
Quest identity and safe network preconditions, enabled port 5555, connected
the endpoint, matched its identity to the USB observation, and passed the full
Quest doctor. The endpoint/identity receipt was private controller state with
mode `0600`; no address or serial entered Git or the common result.

An isolated second host ADB server was then restricted to the wireless
endpoint. The ordinary private-inventory command still requested the USB
serial, observed that transport absent, loaded the hashed local receipt,
connected and revalidated the endpoint, and returned a ready common doctor
with `transport: wireless` and every check passing. The physical cable remained
attached, so this was an isolated ADB-inventory proof rather than a literal
unplug. The exact endpoint route itself was live; missing USB fallback and all
identity checks executed against the physical headset.

Twenty Quest tests cover address/security/lease gates, exact binding, fallback,
identity drift, and observed disable. Two shared-ADB tests and 62 common-client
tests passed, as did compile and diff checks. Wireless disable was not invoked
live because the requested final state was to leave the convenient route
enabled; its device/receipt effects are unit-tested.
