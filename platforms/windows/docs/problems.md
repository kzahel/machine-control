# Running Problems and Improvement Notes

This is a living record of concrete gaps encountered while using WinVM
Testbed. Keep observed behavior, effect, workaround, and a likely improvement
direction together so later work can reproduce the problem.

## Observed 2026-08-04 during 200 OK `v0.1.6` smoke

### Provider screenshots do not share the coordinate space used by `click`

`winvm screenshot` captures the full macOS UTM window with
`screencapture -l`. On the observed Retina host the PNG was 2798×2050 and
included UTM chrome/title-bar pixels, while the guest display and UTM mouse
API used roughly half-scale guest coordinates.

Effect: a point read from the screenshot cannot be passed directly to
`winvm click`; it needs an undocumented scale and title-bar transform. This
made WebView-only controls need trial-and-error clicks.

Possible direction: normalize screenshots to the guest viewport as LinuxVM
and MacVM do, or emit the exact screenshot-to-guest transform alongside the
path. Until then, document that the screenshot is raw host-window pixels even
though `click` accepts title-bar-free guest pixels.

### UIA invoke can report dispatch without an application transition

WinApp's InvokePattern reported that the NSIS installer's **Finish** button
was invoked, but the installer remained on the same page and the application
did not launch. The semantic `click` operation on the same named button did
advance the installer and launch the app.

Effect: a successful `ui invoke` response is not proof that the target handled
the action. Workaround: re-inspect the window after every material action and
retry with semantic click when the transition did not occur.

Possible direction: add this warning and the `click` fallback to the UI guide,
and consider an optional action helper that waits for a window/tree change.

### Embedded WebView content has no semantic driver

The 200 OK Tauri frame was discoverable, but its WebView2 controls were absent
from UIA. This limit is already noted in the README, but it is consequential:
settings, switches, server controls, and inline messages required screenshots,
raw clicks, and keyboard focus traversal. That path is substantially less
reliable than WinApp's native-control automation and made a visually clipped
dialog difficult to inspect.

Possible direction: add a WebView2/CDP-capable driver or a documented
application opt-in that exposes embedded web content to accessibility tooling.
