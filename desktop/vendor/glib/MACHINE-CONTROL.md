# GLib compatibility backport

This is the published `glib` 0.18.5 crate from crates.io, under its original
MIT license (`LICENSE` and `COPYRIGHT`). The upstream crate SHA-256 is
`233daaf6e83ae6a12a52055f568f9d7cf4671dabb78ff9560ab6da230ce00ee5`.

Tauri's GTK3/WebKitGTK dependencies require GLib 0.18. There is no published
0.18 release containing the fix for
[GHSA-wrw7-89jp-8q8g / RUSTSEC-2024-0429](https://rustsec.org/advisories/RUSTSEC-2024-0429.html).
Changing the direct dependency to 0.20 would leave the vulnerable 0.18 copy
in the graph and introduce incompatible GLib types.

The only production-source change is the upstream fix in
[`VariantStrIter::impl_get`](src/variant_iter.rs): make the C output pointer
mutable and pass `&mut p` instead of `&p`. Upstream
[PR 1343](https://github.com/gtk-rs/gtk-rs-core/pull/1343), merged as
`05dff0ee696f9bcd8617cd48c4b812d046d440cb`, owns the original fix.
The package version remains honest at 0.18.5; this is a local backport, not
an upstream release. Cargo resolves every registry use through the path patch
in `desktop/src-tauri/Cargo.toml`.

`tests/variant_str_iter_backport.rs` exercises forward, reverse and mixed
iteration in an optimized build, where the original invalid pointer writes
can be eliminated by the compiler:

```sh
cargo test --manifest-path desktop/vendor/glib/Cargo.toml --release \
  --test variant_str_iter_backport
```

This requires the platform GLib/GObject/GIO development libraries. The test
also runs in Linux desktop CI. Remove the patch and this directory when the
Tauri/GTK dependency chain accepts a fixed upstream release. Future GLib
advisories still require review; this backport fixes only the named issue.

## Static-analysis triage

The initial CodeQL Rust scan conflates the generic `from_glib_none`,
`from_glib_full`, and `from_glib` implementations: its reported paths connect
the console charset's `char*` to `GObject`, boxed-test, and `GValue` converters,
or a null-checked `GError*` to `GObject`/`GValue`. Those trait instantiations are
incompatible in Rust. It similarly connects the UUID-validation boolean to a
log-level conversion and labels that boolean a logged secret. These are
reviewed false positives, not changes to the upstream pointer code.

The `PtrSlice::truncate` report conflates dropping the pointer wrapper stored
in an array slot with deallocating the slot itself. The container retains its
allocation while the element's destructor releases its pointee; writing the
null terminator into that slot remains valid. The four upstream optimized
`collections::ptr_slice` tests exercise pointer ownership. The added
`pointer_slice_retains_storage_after_dropping_elements` integration test
exercises truncation followed by reuse of the retained storage.
Security queries remain enabled; future reports need individual review.
