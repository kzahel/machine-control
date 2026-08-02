# ChromeOS Testbed

CLI tools for managing ChromeOS development devices. No dependencies beyond bash and SSH.

## Skill

The skill definition is at `skills/SKILL.md`. Other projects can reference it for ChromeOS device management.

## CLI

`bin/chromeos <command>` — run `bin/chromeos help` for usage.

Key commands: `doctor`, `smoke-test`, `diagnostics`, `fix-ssh`,
`fix-devtools`, `screenshot`, `desktop-tap`, `desktop-wait`, `adb-status`,
`adb-connect`, `tap`, `type`, `shortcut`, `vt2`, `gui`, `info`, `deploy`,
`power-status`, `keep-awake`, `restore-power`, `shell`.

## Prerequisites

- SSH host `chromeos-testbed` configured in `~/.ssh/config` (port 2223, root user)
- Chromebook in developer mode with SSH bootstrapped (see `scripts/bootstrap.sh`)

## SSH to Chromebook

Always set PATH when running commands via SSH. ChromeOS has a minimal default PATH that's missing standard locations:

```bash
ssh chromeos-testbed "export PATH=/bin:/usr/bin:/usr/local/bin:\$PATH; <command>"
```

## Architecture

```
Dev Machine                     Chromebook (VT2 root)
┌──────────────────┐            ┌──────────────────┐
│ bin/chromeos      │    SSH     │ client.py         │
│ (bash CLI)        │ ────────► │ (evdev input      │
│                   │   :2223   │  + screenshots)   │
└──────────────────┘            └──────────────────┘
```

- `client.py` runs on the Chromebook, accepts JSON commands via stdin, returns JSON on stdout
- `bin/chromeos` deploys `client.py` automatically when needed and sends commands over SSH
- `scripts/` contains standalone fix/diagnostic scripts

## File Locations on Chromebook

| Path | Persists across updates? | Description |
|------|--------------------------|-------------|
| `/mnt/stateful_partition/etc/ssh/` | Yes | SSH keys, start_sshd.sh |
| `/mnt/stateful_partition/c2/client.py` | Yes | Input client |
| `/etc/chrome_dev.conf` | No (reset by updates) | Chrome flags |

## Deploying Changes to Chromebook

When `client.py`, `cdp.py`, `daemon.py`, or `drm_screenshot.py` are modified, ask the user if the changes should be synced to chromeos-testbed. The answer is almost always yes. Deploy with:

```bash
scp <file> chromeos-testbed:/mnt/stateful_partition/c2/<file>
```

## Git Commit Policy

Do NOT include `Co-Authored-By` lines referencing Claude, AI, or Anthropic in commit messages.
