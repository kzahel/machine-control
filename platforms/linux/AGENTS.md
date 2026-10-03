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

Routine lifecycle, administration, and target-native desktop work uses an
ordinary claim. Provider screenshot and input recovery requires a claim
acquired with `--disruptive`. If unplanned outer recovery becomes necessary,
release the ordinary claim and acquire a new disruptive claim with a truthful
recovery reason; do not reuse the released ID. A platform-owner outer-UI
prohibition remains absolute.

Before changing guest bootstrap or recovery, read `docs/bootstrap.md`. Before
changing AT-SPI or coordinate behavior, read `docs/ui-automation.md`. Preserve
the three independent recovery layers: QEMU guest agent, AT-SPI inside the
interactive session, and the visible UTM window.

Always inspect the selected controller's private credential inventory before
login/unlock or asking for human entry. Follow the repository's
[credential contract](../../docs/target-registry.md#credentials-and-private-data):
store VM passwords in the canonical untracked controller-local secret file,
with only its locator in private inventory. Use a supported secret-safe route;
missing metadata/file or missing delivery support is a specific recovery gap,
not a blanket requirement for human authentication. Never commit credentials,
private keys, portal tokens or machine-specific identifiers. Keep `config.local`,
generated captures and command artifacts untracked.

Before accepting or promoting a newly provisioned appliance, follow the
[credential handoff](docs/bootstrap.md#required-credential-handoff-before-promotion)
and run `bin/linuxvm credential verify --json` under its exact-target claim.
An operationally ready desktop or existing secret file is insufficient; require
the factory's `credential-handoff` and `promotion` evidence. Password-free
profiles are explicit and verified, never inferred from absent metadata.

Run `tests/smoke.sh` before committing behavior changes. Shell, Python, and
Swift checks must be warning-free.
