# Quest Testbed Agent Guide

This platform directory is the canonical public source. Do not make
implementation changes in the legacy `quest-testbed` checkout.

This repository owns project-neutral control of physical Meta Quest headsets
over ADB. Keep builds, application-specific assets and arguments, host XR
runtimes, readiness markers, performance policy, and acceptance assertions in
the consuming project.

Start with `bin/quest doctor`. Never select the first arbitrary Android device:
resolve an explicit serial or prove the single authorized hardware device is a
Quest. Keep serials, account details, APK payloads, and controller-local paths
out of this public repository.

Treat the recovery journal as a device lease. Record state before mutation,
refuse live or foreign leases, and retain the journal whenever critical
cleanup fails. The safe final state has the proximity override cleared and the
headset asleep. Do not add full shutdown, root, factory-reset, broad
package-kill, or device-policy behavior.

Meta proximity and VR power-manager shell hooks are undocumented vendor
details. Keep them capability-probed and best effort. Do not weaken the
standard ADB authorization model to compensate for a vendor-hook failure.

Run `python3 -m unittest discover -s tests -v` and
`python3 -m compileall -q quest.py tests` before committing behavior changes.
Run `bin/quest doctor` and an interruption/cleanup session against physical
hardware when access or device lifecycle behavior changes.
