# Steam Deck Testbed Agent Guide

This platform directory is the canonical public source. Do not make
implementation changes in the legacy `steamdeck-testbed` checkout.

This repository owns project-neutral control of a physical Steam Deck over
Valve's SteamOS Devkit SSH path. Keep builds, game-specific assets, launch
policy, persistence, and acceptance assertions in the consuming project.

Start with `bin/steamdeck doctor`. Keep hostnames, addresses, private keys,
Steam accounts, and other machine-specific state out of this public
repository. Use `config.local` or SSH configuration for local overrides.

The CLI must preserve strict host-key checking and validate every Devkit
upload directory before using `rsync --delete`. Do not unlock the SteamOS root
filesystem, enable unrestricted SSH, change passwords, or require root access.

Run `python3 -m unittest discover -s tests -v` and
`python3 -m compileall -q steamdeck.py tests` before committing behavior
changes. Run `bin/steamdeck doctor` against physical hardware when access or
device behavior changes.
