import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";

test("the store ZIP includes every imported runtime module", async () => {
  const directory = await mkdtemp(join(tmpdir(), "mc-extension-package-"));
  try {
    execFileSync("python3", ["providers/chrome-extension/package.py", directory]);
    const result = execFileSync("python3", ["-c", `
import pathlib,re,sys,zipfile,json
p=pathlib.Path(sys.argv[1]); build=json.loads((p/'build.json').read_text())
with zipfile.ZipFile(p/build['filename']) as z:
    names=set(z.namelist())
    assert 'key' not in json.loads(z.read('manifest.json'))
    for name in names:
        if name.endswith('.js'):
            for module in re.findall(r'from\\s+["\\\']\\./([^"\\\']+)["\\\']', z.read(name).decode()):
                assert module in names, (name,module)
    print('presentation.js' in names)
`, directory], {encoding:"utf8"});
    assert.equal(result.trim(), "True");
  } finally { await rm(directory, {recursive:true, force:true}); }
});
