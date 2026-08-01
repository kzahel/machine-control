# Guest Auto-Logon

Auto-logon is optional and must be explicitly authorized for the individual
test appliance. It trades login security for unattended access to the Windows
interactive session after a cold boot.

Use Microsoft's signed [Sysinternals Autologon utility][autologon] inside the
guest. It stores the credential as an LSA secret instead of the plaintext
`DefaultPassword` Winlogon registry value. A local administrator can still
retrieve an LSA secret, so auto-logon is not appropriate for a guest containing
sensitive data.

1. Download `AutoLogon.zip` from the official Microsoft Sysinternals site.
2. Extract the executable matching the guest architecture.
3. Verify that `Get-AuthenticodeSignature` reports a valid Microsoft signer.
4. Run Autologon in the interactive Windows session, enter the guest-local
   account credential, and select **Enable**.
5. Run `bin/winvm down`, then `bin/winvm up`, and verify that
   `bin/winvm doctor` reaches the interactive UI relay without manual input.

Never pass the password as a `winvm` argument, store it in `config.local`, or
write it to repository files or command output. Holding Shift during boot
bypasses auto-logon for that login. Use the Autologon utility's **Disable**
action to remove the configuration.

[autologon]: https://learn.microsoft.com/en-us/sysinternals/downloads/autologon
