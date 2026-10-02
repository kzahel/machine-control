# python-build-standalone

Upstream: [astral-sh/python-build-standalone](https://github.com/astral-sh/python-build-standalone).

**Current:** The build project's declared top-level license is
[MPL-2.0](https://github.com/astral-sh/python-build-standalone/blob/63249f9a31f23542d5a58754aed0b93cc432e761/LICENSE).
Its generated distributions contain CPython under the PSF/Python license stack
and native dependencies under their own narrower terms, including OpenSSL,
SQLite, libffi, compression and optional Tk libraries. The top-level build-tool
license is not a license assertion for every generated binary. Preserve
CPython's shipped `LICENSE.txt` and upstream component notices under
[`desktop/python-licenses`](../../desktop/python-licenses); the CLI ships no pip
site-packages. Exact archive pins live in the desktop runtime lockfile because
they are adopted package inputs, not disposable experiments.

## Fit and evidence

**Decision:** Use digest-pinned relocatable `install_only_stripped` distributions
to preserve a Python CLI without requiring users to install Python. This is a
packaging dependency, not a desktop control provider or resident replacement.
Native semantics and OS permissions remain with the existing adapters.

**Current:** Mac ARM64 is **built** and exercised through the staged CLI's
isolated interpreter. Intel Mac, Windows x64/ARM64 and Linux x64/ARM64 have exact
archive pins but are not execution-accepted by this evidence. Source review
covers archive filtering, internal link flattening, runtime isolation and
whole-payload inventory; it does not establish signed end-user acceptance.
The [installed CLI topic](../../topics/installed-agent-cli.md) owns adoption and
remaining acceptance direction.
