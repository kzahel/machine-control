# Adjacent Projects and Benchmarks

This ledger keeps discovered, pinned, or adjacent projects visible before they
earn full provider dossiers. Evidence levels follow the
[corpus guide](README.md#evidence-levels). License fields describe the
repository's declared top-level terms only.

| Project | Declared license | Evidence | Why it matters / why no dossier yet |
| --- | --- | --- | --- |
| [Playwright](https://playwright.dev/docs/browsers) | [Apache-2.0](https://github.com/microsoft/playwright/blob/main/LICENSE) | `upstream-claimed`; official docs reviewed 2026-08-25 | Deep browser automation across Chromium, WebKit, and Firefox, with mobile browser profiles and experimental Electron support. It is the preferred complementary page-level comparison, not a whole-machine lifecycle or system-UI layer. |
| [Appium core and drivers](https://appium.io/docs/en/latest/intro/) | [Apache-2.0](https://github.com/appium/appium/blob/master/LICENSE) | `upstream-claimed`; official docs reviewed 2026-08-25 | A WebDriver-based server, client, plugin, and driver ecosystem spanning mobile, web, and driver-dependent desktop automation. It is a strong device-native integration comparison; target inventory, shared-target claims, and testbed lifecycle remain separate infrastructure concerns. |
| [BrowserStack](https://www.browserstack.com/docs/) | Commercial service; no open-source top-level distribution reviewed | `upstream-claimed`; official docs reviewed 2026-08-25 | Managed and self-hosted browser automation plus a real-device mobile-app cloud that runs frameworks including Playwright and Appium. It is an infrastructure and capacity comparison rather than an owned target-native contract. |
| [Microsoft UFO](https://github.com/microsoft/UFO) | MIT | `source-reviewed` at broad architecture level; exact spike pin exists | Deep Windows UIA/Win32 agent plus multi-device orchestration. Its agent hierarchy overlaps YepAnywhere; provider-level behavior has not been isolated. |
| [OSWorld](https://github.com/xlang-ai/OSWorld) | Apache-2.0 | `source-reviewed` as a benchmark; exact spike pin exists | Desktop task/environment and evaluation corpus, not a resident semantic provider. Useful conformance-task context. |
| [ChromeOS Tast](https://chromium.googlesource.com/chromiumos/platform/tast) and [Tast tests](https://chromium.googlesource.com/chromiumos/platform/tast-tests) | BSD-3-Clause-style ChromiumOS license | `source-reviewed` at framework level; exact spike pins exist | Native ChromeOS testing and fixtures; not the outside agent facade. Useful for platform assertions and fixture ideas. |
| [Appium Mac2 Driver](https://github.com/appium/appium-mac2-driver) | Apache-2.0 | `upstream-claimed`; exact spike pin exists | The macOS-specific member of the Appium ecosystem above. It needs a focused comparison with AX-native Cua/Peekaboo before dossier promotion. |
| [Windows-MCP](https://github.com/CursorTouch/Windows-MCP) | Review pending | `discovered` | Windows computer-use MCP candidate; no source or license review in the current corpus. |
| [mcp-windows](https://github.com/sbroenne/mcp-windows) | Review pending | `discovered` | Windows UIA-by-name provider; no source or live comparison yet. |
| [linux-desktop-mcp](https://github.com/BeckhamLabsLLC/linux-desktop-mcp) | Review pending | `discovered` | AT-SPI plus X11/system-wide input context; private-compositor isolation appears stronger for test appliances. |
| [Agent for macOS](https://github.com/macos26/agent) | Review pending | `discovered` | Broad local agent with AX, scripting, user service, and privileged helper rather than a narrow provider. |

The spike's exact pin registry is
[`reference-pins.json`](../../machine-control-spike/reference-pins.json).
Promote a project to `providers/` when source review establishes a distinct
architecture lesson or a measured platform gap makes it a real candidate.
