# Local vendor references

Scripts here extract local, Git-ignored reference copies of third-party
components that Machine Control studies or benchmarks against. Extracted
content stays on the machine that produced it; only the scripts and this note
are tracked.

## Codex Computer Use (Sky)

```bash
research/vendor/extract-sky-reference.py            # copy as installed
research/vendor/extract-sky-reference.py --format   # also pretty-print JS (npx prettier)
```

The script copies the `@oai` JavaScript packages bundled in the installed
ChatGPT desktop app (minified JavaScript, TypeScript declarations, Markdown
documentation and package manifests) and the latest cached Codex plugins for
Computer Use and browser use into `research/vendor/sky/<app-version>/`. A
`manifest.json` records the app and package versions, signing team, file
hashes and the native service's version and executable hash. Third-party
`node_modules` and native executables are not copied.

The components are proprietary. Use the copy to understand the interface and
behaviour; do not commit it, publish it, or copy its code or text into
Machine Control. Findings belong in the
[Sky dossier](../providers/sky-computer-use.md) in our own words.
