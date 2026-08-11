# ChromeOS Testbed Agent Guide

This platform directory is the canonical public source. Do not make
implementation changes in the legacy `chromeos-testbed` checkout.

Read [`skills/SKILL.md`](skills/SKILL.md) before operating a ChromeOS target.
Read [`CLAUDE.md`](CLAUDE.md) for repository architecture, deployment, and
commit policy inherited from the original focused source.

Concrete SSH aliases, endpoints, account state, and login material belong in
the controller's private inventory or local configuration. Never commit them,
device captures, or diagnostics here.

Run the dependency-free unit tests and shell syntax checks before committing
behavior changes. Live doctor and smoke commands must use an already
authorized device and must not repair, reboot, or log in unless the user asked
for that mutation.
