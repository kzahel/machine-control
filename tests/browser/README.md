# Focused native relay smoke

`relay-smoke.py` runs ten bounded checks in an exclusively claimed dedicated
Windows or GNOME Wayland Linux VM. It covers Off, extension connection,
independent HTTP click and PNG effects, typed dialogs, stalled evaluation,
uncertain delivery, release recovery and Stop. Windows checks control-status
responsiveness during an action because its admission channel deliberately
allows only one action at once; Linux checks independent browser discovery.

Use the common CLI to stage and launch it in the active graphical session.
Pass `--platform`, `--runtime`, `--chrome`, `--cdp-client` and a new `--output`
directory. `--chrome` must be a separately identified Chrome for Testing
executable. Use `tests/windows/cdp_socket.py` as the fixture CDP client on both
platforms. Windows also needs the repository's `client/*.py` staged in a
`client` sibling of the runtime directory. Its runtime contains the executable,
native companions and `browser-extension`; Linux uses `prepare-linux.py` output.
Keep Linux's real session `XDG_RUNTIME_DIR` and user D-Bus environment.

The inherited operator fixture arms browser and DevTools scopes. Windows then
opens a retained public control session. This exercises native authorization
and the bundled unpacked extension; it does not qualify installed Settings,
protected desktop control, store rollout or signed packages.

The caller owns claims, staging and original-power restoration. Inspect
`result.json`, require `passed: true` and verify owned processes are absent
before removing staging. The actor restores its temporary native-host
registration; `registration-before.json` preserves the prior Windows value
for explicit recovery if hard termination prevents cleanup. Keep evidence and
concrete target identities private. `--no-sandbox` is an explicit empty Linux
VM fixture choice, never a change to OS policy or a production-browser claim.
