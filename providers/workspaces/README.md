# Workspace Receipt Store

This provider-neutral helper stores private receipts for VM workspaces created
or selected by authoritative platform adapters. The common coordinator never
reads this store directly.

Each receipt binds an opaque public handle to the private provider kind,
target identity, optional source identity, requested intent, actual mechanism,
retention, cleanup policy, and last observed state. Receipt directories are
mode `0700` and receipt files are mode `0600` on POSIX hosts.

`inventory` and `gc` emit only the normalized public projection. Provider
adapters may read an allowlisted private field while rechecking an exact
hypervisor identity. `forget` removes only the receipt; an adapter must first
prove that the corresponding provider resource was safely released or is
already absent.

This helper owns neither hypervisor operations nor policy. UTM, Tart, and a
future libvirt provider remain responsible for locking, capacity checks,
source protection, stop/delete behavior, and fresh identity verification.
