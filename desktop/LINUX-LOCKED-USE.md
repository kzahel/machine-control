# Covered desktop access on Ubuntu

The Machine Control Debian package supports the existing local GNOME 50
Wayland session. The feature uses the account's local Ubuntu password and
requires the GNOME lock screen. Package and hardware qualification are
tracked in the [Linux locked-use topic](../topics/linux-locked-use.md).

## Set up from the unlocked desktop

1. Turn **Agent access** off. In **Permissions → Covered desktop while
   locked**, choose **Open access settings**, then **Set up covered desktop
   access**. Enter the Ubuntu account password in the native dialog and approve
   the system prompt. The helper verifies and stores an encrypted copy.
   Approve the read-only physical activity observer if requested.
2. Sign out and back in if the app says GNOME needs to load the extension.
   This can be necessary after a first install or package upgrade.
3. Turn on **Allow prepared tasks behind an opaque cover**. Enable
   **Desktop access** and select **Start immediately** if an agent needs
   unattended access while the console is locked.

Local mouse movement, a button press, or keyboard input relocks the console
and pauses covered work until you unlock it yourself. Use **Stop access** to
revoke access. **Update saved password** replaces the enrollment after an
Ubuntu password change. **Remove unlock setup** erases the saved credential.

If an unlock is interrupted, Machine Control ends the task and relocks the
console. It keeps the encrypted password for a fresh authorized task. A
password change or an explicit rejection requires updating the saved password.

## Start a task

```sh
machine-control --target TARGET control stream --surface desktop --prepared-console \
  --reason 'Work in the covered desktop'
```

Pass the target's claim when required. The app starts one covered unlock at
acceptance. The first operation waits for the helper and the compositor to
verify it. Capture uses a private offscreen render. Pointer and keyboard
operations go to the verified foreground application. Keyboard input supports
plain application keys and selected Control and Shift combinations. Text
entry uses the current clipboard selection and an application paste.

Closing the owner, expiry, or a safety failure starts relocking. The helper
uses the installed GDM password conversation and the same logind session
throughout. It holds the credential in a root-owned store and has no
credential-export operation. This is a trust boundary around the password
and native unlock. Processes with a shell as the desktop user already have
the permissions of that account.

Browser-only access has its own setting and can leave the console locked.

In the current source, **Start at login** and **Restore access when Machine
Control starts** can bring back **Until I turn it off** access after GNOME
sign-in, including when the session is already locked. To run covered tasks
from that state, complete the covered setup above. GDM automatic login and
any lock-on-login hook are GNOME configuration. A password-protected GNOME
Login keyring may still need to be unlocked separately after automatic login.
