# References

External repos checked out under `references/` for code reference. All are shallow clones (depth=1).

## input-over-ssh

- **URL:** https://github.com/martinetd/input-over-ssh.git
- **Clone:** shallow (depth=1)
- **Description:** Tool for forwarding input devices over SSH using evdev.

## platform2

- **URL:** https://chromium.googlesource.com/chromiumos/platform2
- **Clone:** shallow (depth=1), blobless (`--filter=blob:none`), sparse checkout
- **Sparse paths:** `screen-capture-utils`
- **Description:** ChromeOS platform utilities. Only the screen capture code is checked out.

## python-evdev

- **URL:** https://github.com/gvalkov/python-evdev.git
- **Clone:** shallow (depth=1)
- **Description:** Python bindings for the Linux evdev input subsystem.

## tast-tests

- **URL:** https://chromium.googlesource.com/chromiumos/platform/tast-tests
- **Clone:** shallow (depth=1), blobless (`--filter=blob:none`), sparse checkout
- **Sparse paths:**
  - `src/chromiumos/tast/local/input`
  - `src/chromiumos/tast/local/screenshot`
  - `src/go.chromium.org/tast-tests/cros/local/bundles/cros/graphics`
  - `src/go.chromium.org/tast-tests/cros/local/chrome/uiauto/faillog`
  - `src/go.chromium.org/tast-tests/cros/local/screenshot`
- **Description:** ChromeOS integration tests. Only input, screenshot, and graphics test code is checked out.
