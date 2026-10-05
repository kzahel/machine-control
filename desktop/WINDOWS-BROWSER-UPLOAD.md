# Windows browser file uploads

This is an unreleased desktop development feature. Browser file attachment
uses the existing Machine Control Chrome extension; no UAC helper is needed.

## Usage

Set up the browser extension in **Permissions**, load it in Chrome, and enable
**Browser tabs** access. Browser access can attach named local files to websites.
An agent needs a live control session, as for other browser operations.

Find a file input or upload button in `browser snapshot`, then use its current
reference:

```text
machine-control --target TARGET --claim CLAIM browser upload \
  --reference REFERENCE --file "C:\Documents\report.pdf"
```

Repeat `--file` for multiple files when the page permits them. CLI and SDK use
the same `browser.upload` request with `reference` and a `files` array. Paths
belong to the selected target, even when the caller is on another computer.
This operation does not copy controller files into the target.

## Behavior and limits

A file input receives files through CDP `DOM.setFileInputFiles`. For a button,
the extension intercepts Chrome's file chooser event and attaches files to the
identified input without opening the operating system dialog. A button that
does not open a chooser returns a bounded refusal. Chromium/CDP is the provider;
Firefox, Safari and other browser implementations are not qualified by this.

Requests may name 1–20 existing, readable regular files on local drive-qualified
paths. The resident checks the entire batch before forwarding. Relative, UNC,
device, alternate-stream and network-drive paths are refused. Reparse links,
hidden/system entries, dot-prefixed components and AppData storage are refused.
These checks are not containment against unrestricted same-user shell access:
Chrome reopens paths, and another local process can replace files after checking.

Upload requires browser scope, not unrestricted DevTools or desktop control.
Pending approval, Pause, Stop, expiry, loss of ownership and desktop/provider
generation changes retain their existing fences. Superseded references refuse.
The product does not retry uncertain delivery or operate the OS picker as an
automatic fallback.

An accepted result confirms attachment delivery, not successful website upload.
The agent must check the website's result independently. Local file paths and
contents are omitted from ordinary audit history.

[Tactical 098](../docs/tactical/098-windows-browser-upload.md) records actual
candidate validation and the remaining release/platform qualification gates.
