# LinuxVM Testbed Agent Guide

This platform directory is the canonical public source. Do not make
implementation changes in the legacy `linuxvm-testbed` checkout.

LinuxVM Testbed operates an Ubuntu Wayland desktop inside UTM from a macOS
host. Keep lifecycle/transport in `providers/`, guest behavior in `guests/`,
and agent-facing commands in `bin/`.

Before changing guest bootstrap or recovery, read `docs/bootstrap.md`. Before
changing AT-SPI or coordinate behavior, read `docs/ui-automation.md`. Preserve
the three independent recovery layers: QEMU guest agent, AT-SPI inside the
interactive session, and the visible UTM window.

Never store passwords, private keys, portal restore tokens, or machine-specific
identifiers. Ask the user to enter authentication directly in the guest. Keep
`config.local`, generated captures, and command artifacts untracked.

Run `tests/smoke.sh` before committing behavior changes. Shell, Python, and
Swift checks must be warning-free.
