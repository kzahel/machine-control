# Common client tests

Run the dependency-free adapter tests without live targets:

```bash
python3 -m unittest discover -s tests/client -v
```

With an accepted target already running, run the shared guarded workflow:

```bash
tests/client/live-desktop-conformance.sh windows
tests/client/live-desktop-conformance.sh macos
tests/client/live-desktop-conformance.sh linux
```

The live script uses only `bin/machine-control`. Platform cases provide fixture
setup, independent-effect reads, and cleanup through the explicit `testbed` or
`os` escape hatches. The ordinary status, capabilities, local/outside parity,
snapshot, action, capture, and artifact operations all use the common client.
Every run forces the relevant outer-UI prohibition and emits one minimized
`machine-control-common-desktop-conformance/v0` result.
