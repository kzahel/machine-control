# Optional Windows unattended unlock

Status: implementation preview; native acceptance pending. Do not describe a
successful signature check or administrator approval as proof of an unlock.

The workstation package can install a separate LocalSystem service that unlocks
an existing, locked console account. It exposes only status and a guarded unlock
transaction. Installation alone leaves it unarmed. The ordinary workstation host
and the dedicated-appliance broker keep their existing contracts.

## Administrator setup

Run these from the verified, extracted distribution in an interactive Windows
session. Each action requests UAC elevation when required.

```powershell
.\unlock-setup.exe Install example
.\unlock-setup.exe Arm example C:\path\to\approval.json
.\unlock-setup.exe Revoke example
.\unlock-setup.exe Uninstall example
```

`Arm` additionally shows an elevated confirmation containing the exact local
Windows account/SID, transport account/SID, controller public-key fingerprint,
and expiration. Its default button declines. A cancelled UAC or confirmation
creates no grant. Copy only the public approval proposal to Windows; keep the
controller private key where the controller runs.

The default proposal lasts until revoked. Pass `--hours 8` to the proposal
helper for an eight-hour grant. Expiration limits new credential submissions;
it does not relock an already unlocked desktop. Revoke stops pending attempts
before restarting the unarmed service. Upgrade currently requires explicit
revoke/uninstall/install/re-arm; it never silently preserves authority.

Install and Uninstall use the original distribution's setup entry. Payloads
live under `%ProgramFiles%\MachineControlUnlock\INSTANCE`, and grants under
`%ProgramData%\MachineControlUnlock\INSTANCE`, with administrator/SYSTEM write
access. No Windows password or PIN is stored there. The installed bootstrap may
also run Arm or Revoke. An unsigned development bootstrap built without a release
publisher accepts a proposal (or `-`) and `--allow-unsigned`. Signed release
bootstraps reject this flag and always require publisher/catalog verification.

## Controller preparation

The supplied `unlock-controller.py` is an optional Python 3/OpenSSL controller
helper. It can run on an outside host with access to the target's authenticated
SSH transport. YepAnywhere may implement the same protocol and keep the key in
its own credential store. A controller private key accessible to an unrestricted
same-user agent does not provide containment from that agent.

```sh
python3 unlock-controller.py keygen --key controller.pem --public controller.pub
python3 unlock-controller.py proposal --public controller.pub \
  --target-sid TARGET_ACCOUNT_SID --transport-sid CARRIER_ACCOUNT_SID \
  --output approval.json
```

The target must be a local Windows account. The transport SID identifies the
Windows identity running the installed carrier, which may differ from the target
account. Proposal files and key material are deployment state: keep them outside
source control. The helper refuses to overwrite an existing key or proposal.

For a local Windows controller, the installed binary signs using its local PEM
key and reads a credential from redirected stdin only after authorization and
native field discovery succeed:

```powershell
& "$env:ProgramFiles\MachineControlUnlock\example\machine-control-windows.exe" unlock --status --instance example
# Invoke with a non-echoing credential stream on stdin:
& "$env:ProgramFiles\MachineControlUnlock\example\machine-control-windows.exe" unlock --instance example --grant C:\path\approval.json --key C:\path\controller.pem --kind password
```

For an outside controller, run `unlock-controller.py unlock --instance example
--grant approval.json --key controller.pem --secret-file PRIVATE_CREDENTIAL_FILE
-- CARRIER_COMMAND...`. The carrier command must start the installed executable
on Windows with `unlock --relay --instance example`, over authenticated SSH or
another explicitly trusted transport. Machine Control testbeds must carry their
exclusive target claim on that transport. Neither keys nor credentials belong
in command arguments, environment variables or ordinary JSON.

## Protocol and limits

The local pipe is `machine-control-unlock-INSTANCE`. The Windows client checks
its server PID against the running service PID reported by SCM before sending
a credential. The service checks the pipe caller SID against the administrator's
grant and authenticates the controller separately with P-256/SHA-256 signatures.

1. A bounded JSON line requests `unlock` and `credentialKind` (`password` or `pin`).
2. The service returns `stage: challenge` and an exact UTF-8 JSON string binding
   the protocol, instance, service generation, session epoch/ID, grant revision,
   account SID, controller fingerprint, credential kind, random nonce and expiry.
3. The controller verifies those bindings against its approved proposal and
   returns a base64 DER-encoded ECDSA signature over the exact challenge bytes.
4. The service discovers and focuses the stock credential field. Only then does
   `stage: ready` authorize reading the credential source. The next frame is a
   two-byte little-endian byte count followed by 1–256 UTF-8 bytes, with no newline.
5. The service and protected worker recheck authority, account and field before
   delivery and submission. The result distinguishes delivery from WTS/desktop
   evidence. A failed or unknown result must never be retried automatically.

Fresh challenges prevent proof replay. Session events, changed grants, expiry
and revocation invalidate pending authority. The secret is forwarded once through
a SYSTEM-only pipe and buffers are cleared on a best-effort basis. The service
stores no credential. Grant approval is not the Windows credential itself.

Initial coverage is deliberately limited to existing local console accounts
with a unique local account/display-name mapping and the observed stock Windows
credential UI. Domain/cloud accounts, ambiguous display names, account switching,
no-user login, preboot, biometric credentials and general UAC delegation are not
supported by this component. Provider discovery or focus uncertainty refuses
before reading the credential. Concurrent physical input can still disturb an
attempt; this is not an OS-wide input transaction or a protection boundary
against administrators or SYSTEM. Stock Windows security policy remains intact.
