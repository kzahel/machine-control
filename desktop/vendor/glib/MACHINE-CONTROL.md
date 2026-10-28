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
