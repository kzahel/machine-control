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

test("unpacked staging preserves its ID and excludes polluted source caches", async () => {
  const directory = await mkdtemp(join(tmpdir(), "mc-extension-unpacked-"));
  try {
    execFileSync("python3", ["-B", "-c", `
import importlib.util,json,pathlib,shutil,sys
spec=importlib.util.spec_from_file_location('extension_package','providers/chrome-extension/package.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
root=pathlib.Path(sys.argv[1]); source=root/'source'
shutil.copytree(package.ROOT,source,ignore=shutil.ignore_patterns('__pycache__'))
cache=source/'__pycache__';cache.mkdir();(cache/'fixture.pyc').write_bytes(b'fixture')
package.ROOT=source; output=root/'unpacked';package.write_unpacked(output)
names={p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
assert names=={'manifest.json',*package.FILES}, names
assert json.loads((output/'manifest.json').read_text())['key']==json.loads((source/'manifest.json').read_text())['key']
assert (cache/'fixture.pyc').read_bytes()==b'fixture', 'staging must not alter its source'
try:package.write_unpacked(output)
except FileExistsError:pass
else:raise AssertionError('existing directory was overwritten')
`, directory]);
  } finally { await rm(directory, {recursive:true, force:true}); }
});
