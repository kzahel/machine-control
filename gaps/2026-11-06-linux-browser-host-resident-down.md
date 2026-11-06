# Linux native messaging host crashes while the resident is down

Topic: `browser-control`

Status: **Open — observed during Linux update acceptance; reconnection works.**

## Observations

During the 2026-11-06 Linux ARM64 update runs, Chrome kept retrying the
native messaging host while Machine Control was restarting.
`desktop/native/linux/browser_host.py` connects to the resident's
`desktop.sock` without handling `FileNotFoundError` or
`ConnectionRefusedError`. Each retry while the resident was down produced an
uncaught traceback. Ubuntu's apport then created a crash report and a
visible crash dialog. Once the updated resident was up, the extension
reconnected and Browser access worked.

## Proposed repairs

- Catch connection failures in `browser_host.py` and exit cleanly with a
  closed diagnostic code instead of a traceback, so apport does not file a
  crash.
- Optionally wait briefly for the socket during a known update or restart
  before exiting, so the extension sees fewer disconnects.
