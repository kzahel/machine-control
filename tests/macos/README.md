# macOS conformance

The macOS corpus drives the target-resident facade provided by the sibling
`macvm-testbed` repository. `conformance.sh` runs the same request vocabulary
through two placements:

- `remote`: the host wrapper sends a request through `tart exec`; and
- `local`: `tart exec` launches the installed guest-local client, which calls
  the same private resident socket.

The deterministic AppKit fixture supplies both visible AX state and a separate
file oracle. Tests do not treat an AX or input acknowledgement as proof of an
application effect. The script also checks exact-window artifacts, resident
restart, stale-reference refusal, and System Settings background behavior.

Run it from this repository after selecting a guarded disposable/candidate VM
in the testbed's ignored local configuration:

```bash
tests/macos/conformance.sh
tests/macos/conformance.sh remote
tests/macos/conformance.sh local
```

No target name, guest account, network endpoint, or captured artifact is
written into this repository.
