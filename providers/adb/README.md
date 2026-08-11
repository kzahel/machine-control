# Shared ADB Provider

This dependency-free Python package owns neutral Android Debug Bridge
executable discovery, device enumeration, exact serial transport, shell
execution, and common battery/wake-state parsing. It is reused by the Android
handheld and Quest platform adapters.

It deliberately does not select a device class, decide lifecycle policy,
inspect a phone keyguard, manage Quest proximity, inject credentials, or expose
a generic Android semantic interface. Those responsibilities remain in the
platform profile that can state and test their safety constraints honestly.

Run its unit tests from the repository root:

```bash
python3 -m unittest discover -s providers/adb/tests -v
```
