# Interactive Windows UI Automation

## Session Bridge

Windows OpenSSH processes run in non-interactive session 0. Desktop apps and
their accessibility trees run in a logged-in interactive session. The bridge
crosses that boundary:

```text
bin/winui -> key-only SSH -> ui-client.ps1 -> named pipe
          -> ui-relay.ps1 in interactive session -> winapp.exe
```

The pipe ACL grants access only to the logged-in user and SYSTEM. The relay
runs with the user's normal desktop token, so Windows UIPI still prevents it
from controlling elevated or secure-desktop windows.

## Install and Verify

With SSH working and the Windows desktop logged in:

```bash
bin/winvm deploy-ui
bin/winvm doctor
```

The checked-in deployer is preferable to manual copying. It installs
Microsoft WinApp CLI when absent, deploys all PowerShell files, registers the
interactive-logon task, and checks relay health.

Guest state and logs are stored under:

```text
%LOCALAPPDATA%\winvm-testbed\relay-state.json
%LOCALAPPDATA%\winvm-testbed\relay.log
```

## Discover Before Acting

Packaged applications can have a launcher process, an application process,
and an `ApplicationFrameHost` window. List windows and inspect likely targets:

```bash
bin/winvm ui windows
bin/winvm ui inspect -a notepad --interactive --depth 8
bin/winvm ui inspect -w WINDOW_HANDLE --interactive --depth 8
```

Operate discovered controls semantically:

```bash
bin/winvm ui search Close -w WINDOW_HANDLE
bin/winvm ui invoke Close -w WINDOW_HANDLE
bin/winvm ui focus CONTROL -w WINDOW_HANDLE
bin/winvm ui set-value CONTROL 'new value' -w WINDOW_HANDLE
```

Launch GUI applications through the relay, not raw SSH:

```bash
bin/winvm ui launch notepad.exe
bin/winvm ui launch calc.exe
```

Capture a window to a newly created local temporary directory:

```bash
bin/winvm ui screenshot -a notepad
bin/winvm ui screenshot -w WINDOW_HANDLE
```

WinApp requires a target. Use `bin/winvm screenshot` for the whole visible UTM
window. Run `bin/winui` for convenience commands; `ui ...` and `winapp ...`
provide direct access to the underlying CLI.

## Limits

- After a cold boot, SSH works before login but UI automation waits for an
  interactive login, whether manual or provided by explicitly configured
  guest-local auto-logon.
- Lock screens, consent prompts, and secure desktops require provider-level or
  manual interaction.
- Native apps may expose rich semantic trees; packaged app outer frames and
  embedded webviews may expose only partial controls.
- RustDesk and RDP are useful human-viewing additions, not semantic automation
  channels.

## Uninstall

From an administrative Windows PowerShell session:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$env:LOCALAPPDATA\winvm-testbed\uninstall-ui-relay.ps1"
```

Add `-RemoveInstalledFiles` to remove the deployed relay files too.
