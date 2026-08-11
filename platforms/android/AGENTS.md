# Android Handheld Testbed Agent Guide

This directory is the canonical public source for project-neutral physical
Android handheld control. Use `bin/android-device doctor` before mutation and
always resolve an explicit configured serial when more than one eligible
device is attached.

The neutral ADB transport lives under `providers/adb`; Android phone keyguard,
credential, application, and lifecycle policy remains here. Quest, ARCVM,
emulators, TVs, watches, automotive devices, and other Android derivatives keep
their own target profiles and must not silently inherit handheld policy.

Never put a PIN, password, pattern, device serial, account name, private APK,
or controller-local path in Git, JSON requests, command arguments, environment
variables, logs, captures, or evidence. `unlock` reads one PIN from its
dedicated non-echoing standard-input channel only after exact target and PIN
surface discovery. It submits once and never retries. Do not add credential
clear/reset, device-policy weakening, root, factory reset, or broad package
mutation.

Run `python3 -m unittest discover -s tests -v` and
`python3 -m compileall -q android_device.py tests ../../providers/adb` before
committing behavior changes. Changes to reboot, keyguard, helper delivery, or
credential handling also require proportionate physical-device validation;
never deliberately test an incorrect credential.
