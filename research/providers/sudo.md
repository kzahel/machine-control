# Sudo

**Current:** macOS system sudo is the authentication and elevation
provider for the [native sudo wrapper](../../platforms/macos/sudo/README.md).
The wrapper invokes the OS executable; it redistributes no sudo source.
This route is **conformance-tested** for signed ARM64 helper authentication,
refusal and an independent root effect in a dedicated Mac appliance.
Evidence for this route is recorded in [Tactical 061](../../docs/tactical/061-native-sudo.md).
Linux/ChromeOS askpass integration is untested; Windows has a different
administration mechanism. No cross-platform implementation claim is made.

## Architecture and license

Sudo owns policy, PAM authentication, root execution, and command lifecycle.
Its askpass interface runs a helper whose stdout supplies the password.
[Upstream manual](https://github.com/sudo-project/sudo/blob/main/docs/sudo.man.in)
documents `-A` and that command-form `-k` ignores and does not update cached
credentials. Existing NOPASSWD policy remains effective.

[Upstream license](https://github.com/sudo-project/sudo/blob/main/LICENSE.md)
is principally an ISC-style permissive license with additional per-file
BSD/ISC-style notices. The full upstream license enumerates narrower terms;
this dossier does not replace that audit. Apple distributes its own system
build. The wrapper uses the installed executable without copying its code.

## Integration constraints

**Current:** source review of
[askpass execution](https://github.com/sudo-project/sudo/blob/main/src/tgetpass.c)
shows extra inherited descriptors are closed before helper execution. A
private socket supplies only display context; password bytes use the original
sudo askpass pipe. A one-use endpoint makes a second password attempt refuse.

**Current:** system sudo can be mode 4511, so an ordinary-user static signature
check fails. Exact process path, system file ownership/mode, root effective
identity and kernel platform signing status authenticate that process.
[Apple XNU signing flags](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/kern/cs_blobs.h)
and [csops implementation](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_proc.c)
are the source for this route. The wrapper/helper peer signatures use Security
framework checks against the installed siblings and shared publisher.

**Open:** Touch ID/PAM behavior, non-console sessions, additional OS versions,
and other architectures need their own live evidence. A general root broker,
automatic sudo replacement, and session-wide passwordless authorization are
outside this route.
