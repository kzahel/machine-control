# Project Context

Read `AGENTS.md`, then start with `README.md`. Detailed contracts live in:

- `docs/architecture.md` for layer ownership and command completion.
- `docs/bootstrap.md` for existing-image bring-up and recovery.
- `docs/ui-automation.md` for Wayland, AT-SPI, and outer input behavior.

Do not assume SSH is enabled. The default durable command channel is UTM's
QEMU guest agent, and the default semantic channel is the logged-in user's
AT-SPI session bus.
