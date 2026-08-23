# LinuxVM Testbed Agent Guide

This platform directory is the canonical public source. Do not make
implementation changes in the legacy `linuxvm-testbed` checkout.

LinuxVM Testbed operates an Ubuntu Wayland desktop inside UTM from a macOS
host. Keep lifecycle/transport in `providers/`, guest behavior in `guests/`,
and agent-facing commands in `bin/`.

Start from the repository root with
`bin/machine-control --target linux target doctor`. Once it resolves exact
private identity, acquire an exclusive target-use claim with a reason,
caller-chosen authority, and claimant ID. Carry the returned claim ID with
`--claim` on every operation,
renew it during long work, and release it from cleanup. This metadata is
coordinator-neutral and self-asserted; use identifiers the current execution
environment can truthfully provide, never secrets or private endpoints. If
doctor cannot resolve exact identity, repair the ignored/private inventory and
rerun doctor before claiming or operating the VM.

Before changing guest bootstrap or recovery, read `docs/bootstrap.md`. Before
changing AT-SPI or coordinate behavior, read `docs/ui-automation.md`. Preserve
the three independent recovery layers: QEMU guest agent, AT-SPI inside the
interactive session, and the visible UTM window.

Never store passwords, private keys, portal restore tokens, or machine-specific
identifiers. Ask the user to enter authentication directly in the guest. Keep
`config.local`, generated captures, and command artifacts untracked.

Run `tests/smoke.sh` before committing behavior changes. Shell, Python, and
Swift checks must be warning-free.
