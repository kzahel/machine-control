import test from "node:test";
import assert from "node:assert/strict";
import {
  compareVersions,
  loadDesktopRelease,
  selectDesktopRelease,
} from "../src/lib/desktop-release.ts";
import { GET as windowsDownload } from "../src/pages/download/windows/[arch].ts";
import { GET as download } from "../src/pages/download/macos/[arch].ts";
import { GET as linuxDownload } from "../src/pages/download/linux/[arch]/[format].ts";
const base = "https://github.com/kzahel/machine-control/releases";
function release(version = "0.3.3", prefix = "desktop-v") {
  const tag = prefix + version;
  const names = [
    "latest.json",
    ...["arm64", "x86_64"].flatMap((a) =>
      [`.dmg`, `.app.tar.gz`, `.app.tar.gz.sig`].map(
        (s) => `MachineControl_${version}_${a}${s}`,
      ),
    ),
  ];
  if (compareVersions(version, "0.4.8") >= 0) names.push(
    ...["x64", "arm64"].flatMap((a) => [
      `MachineControl_${version}_${a}-setup.exe`,
      `MachineControl_${version}_${a}-setup.exe.sig`,
      `build-windows-${a}.json`, `payload-windows-${a}.json`,
    ]),
    "build-macos-arm64.json", "build-macos-x86_64.json",
  );
  if (compareVersions(version, "0.5.0") >= 0) names.push(
    ...["amd64", "arm64"].flatMap(a => [
      `MachineControl_${version}_${a}.AppImage`, `MachineControl_${version}_${a}.AppImage.sig`,
      `MachineControl_${version}_${a}.deb`, `MachineControl_${version}_${a}.deb.sig`,
      `build-linux-${a}.json`, `payload-linux-${a}.json`,
    ]),
  );
  return {
    tag_name: tag,
    html_url: `${base}/tag/${tag}`,
    draft: false,
    prerelease: false,
    assets: names.map((name) => ({
      name,
      state: "uploaded",
      size: 100,
      browser_download_url: `${base}/download/${tag}/${encodeURIComponent(name)}`,
    })),
  };
}
function fetcher(releases: unknown = [release()]): typeof fetch {
  return (async () => Response.json(releases)) as typeof fetch;
}
function context(params: Record<string, string>) {
  return { params } as any;
}

test("Linux requires both complete package sets and preserves historical downloads", async () => {
  const unified = release("0.5.0");
  const selected = selectDesktopRelease([unified, release("0.4.8")])!;
  assert.equal(selectDesktopRelease([release("0.4.8")])!.linuxDownloads, null);
  for (const name of ["MachineControl_0.5.0_arm64.AppImage.sig", "payload-linux-amd64.json"])
    assert.throws(() => selectDesktopRelease([{...unified, assets: unified.assets.filter(a => a.name !== name)}, release("0.4.8")]));
  const original = globalThis.fetch;
  try {
    globalThis.fetch = fetcher([unified]);
    for (const arch of ["amd64", "arm64"] as const) for (const format of ["appimage", "deb"] as const) {
      const result = await linuxDownload(context({arch, format}));
      assert.equal(result.status, 302);
      assert.equal(result.headers.get("Location"), selected.linuxDownloads![arch][format]);
    }
    assert.equal((await linuxDownload(context({arch:"x86",format:"deb"}))).status, 404);
    globalThis.fetch = fetcher([release("0.4.8")]);
    assert.equal((await linuxDownload(context({arch:"amd64",format:"appimage"}))).status, 404);
    globalThis.fetch = fetcher([{...unified, assets: []}]);
    assert.equal((await linuxDownload(context({arch:"amd64",format:"deb"}))).status, 503);
  } finally { globalThis.fetch = original; }
});

test("latest desktop selection ignores other products, drafts and prereleases", () => {
  const draft = { ...release("9.0.0"), draft: true };
  const preview = { ...release("8.0.0"), prerelease: true };
  const result = selectDesktopRelease([
    release("10.0.0", "workstation-v"),
    draft,
    preview,
    release("0.3.9"),
    release("0.3.10"),
  ]);
  assert.equal(result?.version, "0.3.10");
  assert.equal(selectDesktopRelease([draft, preview]), null);
  assert.equal(compareVersions("1.0.0", "0.99.99"), 1);
  assert.throws(() => compareVersions("01.0.0", "1.0.0"));
});
test("incomplete or redirected latest assets fail instead of silently downgrading", () => {
  const incomplete = release();
  incomplete.assets.pop();
  assert.throws(() => selectDesktopRelease([incomplete, release("0.3.2")]));
  const external = release();
  external.assets[0].browser_download_url = "https://example.com/evil";
  assert.throws(() => selectDesktopRelease([external]));
  assert.throws(() => selectDesktopRelease({}));
});
test("upstream release failures are surfaced", async () => {
  await assert.rejects(
    loadDesktopRelease(
      (async () => new Response("", { status: 429 })) as typeof fetch,
    ),
  );
});
test("public download routes select each architecture and fail closed", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = fetcher();
    const arm = await download(context({ arch: "arm64" }));
    assert.equal(arm.status, 302);
    assert.match(
      arm.headers.get("Location")!,
      /desktop-v0.3.3\/MachineControl_0.3.3_arm64.dmg$/,
    );
    const intel = await download(context({ arch: "x86_64" }));
    assert.match(intel.headers.get("Location")!, /_x86_64.dmg$/);
    assert.equal((await download(context({ arch: "windows" }))).status, 404);
    globalThis.fetch = fetcher([]);
    assert.equal((await download(context({ arch: "arm64" }))).status, 404);
    globalThis.fetch = (async () => {
      throw new Error("Unavailable");
    }) as typeof fetch;
    assert.equal((await download(context({ arch: "arm64" }))).status, 503);
  } finally {
    globalThis.fetch = original;
  }
});

test("unified release requires both Windows architectures and retains legacy Mac releases", async () => {
  const unified = release("0.4.8");
  const selected = selectDesktopRelease([unified, release("0.3.5")]);
  assert.match(selected!.windowsDownloads!.arm64, /MachineControl_0.4.8_arm64-setup.exe$/);
  assert.equal(selectDesktopRelease([release("0.3.5")])!.windowsDownloads, null);
  for (const name of ["MachineControl_0.4.8_arm64-setup.exe", "payload-windows-x64.json"]) {
    assert.throws(() => selectDesktopRelease([{...unified, assets: unified.assets.filter(a => a.name !== name)}, release("0.3.5")]));
  }
  const original = globalThis.fetch;
  try {
    globalThis.fetch = fetcher([unified]);
    for (const arch of ["x64", "arm64"]) {
      const result = await windowsDownload(context({arch}));
      assert.equal(result.status, 302);
      assert.equal(result.headers.get("Location"), selected!.windowsDownloads![arch as "x64" | "arm64"]);
    }
    assert.equal((await windowsDownload(context({arch: "x86"}))).status, 404);
    globalThis.fetch = fetcher();
    assert.equal((await windowsDownload(context({arch: "x64"}))).status, 404);
    globalThis.fetch = fetcher([{...unified, assets: []}]);
    assert.equal((await windowsDownload(context({arch: "x64"}))).status, 503);
  } finally { globalThis.fetch = original; }
});
