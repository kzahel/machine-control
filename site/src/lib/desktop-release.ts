/** Public desktop releases are independent of the Windows resident package. */
export const REPOSITORY = "kzahel/machine-control";
const BASE = `https://github.com/${REPOSITORY}/releases`;
const VERSION = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;
export type WindowsArch = "x64" | "arm64";
export type MacArch = "arm64" | "x86_64";
export type LinuxArch = "amd64" | "arm64";
type Json = Record<string, unknown>;
export type DesktopRelease = {
  version: string;
  url: string;
  manifestUrl: string;
  downloads: Record<MacArch, string>;
  windowsDownloads: Record<WindowsArch, string> | null;
  linuxDownloads: Record<LinuxArch, { appimage: string; deb: string }> | null;
};
function object(value: unknown): Json {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Invalid release metadata");
  return value as Json;
}
export function versionParts(version: string): number[] {
  if (!VERSION.test(version)) throw new Error("Invalid version");
  const parts = version.split(".").map(Number);
  if (!parts.every(Number.isSafeInteger)) throw new Error("Invalid version");
  return parts;
}
export function compareVersions(a: string, b: string): number {
  const left = versionParts(a),
    right = versionParts(b);
  for (let i = 0; i < 3; i++)
    if (left[i] !== right[i]) return left[i] > right[i] ? 1 : -1;
  return 0;
}
export function selectDesktopRelease(value: unknown): DesktopRelease | null {
  if (!Array.isArray(value)) throw new Error("Invalid release list");
  const releases = value
    .map(object)
    .filter(
      (r) =>
        r.draft === false &&
        r.prerelease === false &&
        typeof r.tag_name === "string" &&
        r.tag_name.startsWith("desktop-v") &&
        VERSION.test(r.tag_name.slice(9)),
    );
  releases.sort((a, b) =>
    compareVersions(
      (b.tag_name as string).slice(9),
      (a.tag_name as string).slice(9),
    ),
  );
  if (!releases.length) return null;
  const release = releases[0];
  const version = (release.tag_name as string).slice(9);
  const url = `${BASE}/tag/desktop-v${version}`;
  if (release.html_url !== url || !Array.isArray(release.assets))
    throw new Error("Invalid desktop release");
  const assets = release.assets.map(object);
  const asset = (name: string) => {
    const matches = assets.filter((a) => a.name === name);
    const expected = `${BASE}/download/desktop-v${version}/${encodeURIComponent(name)}`;
    if (
      matches.length !== 1 ||
      matches[0].browser_download_url !== expected ||
      matches[0].state !== "uploaded" ||
      typeof matches[0].size !== "number" ||
      matches[0].size <= 0
    )
      throw new Error("Incomplete desktop release");
    return expected;
  };
  const downloads = {} as Record<MacArch, string>;
  for (const arch of ["arm64", "x86_64"] as const) {
    downloads[arch] = asset(`MachineControl_${version}_${arch}.dmg`);
    asset(`MachineControl_${version}_${arch}.app.tar.gz`);
    asset(`MachineControl_${version}_${arch}.app.tar.gz.sig`);
  }
  let windowsDownloads: Record<WindowsArch, string> | null = null;
  // Historical desktop releases are Mac-only. Unified releases require every
  // published architecture; never hide missing Windows assets by downgrading.
  if (compareVersions(version, "0.4.8") >= 0) {
    windowsDownloads = {} as Record<WindowsArch, string>;
    for (const arch of ["x64", "arm64"] as const) {
      const installer = `MachineControl_${version}_${arch}-setup.exe`;
      windowsDownloads[arch] = asset(installer);
      asset(installer + ".sig");
      asset(`build-windows-${arch}.json`);
      asset(`payload-windows-${arch}.json`);
    }
    for (const arch of ["arm64", "x86_64"] as const)
      asset(`build-macos-${arch}.json`);
  }
  let linuxDownloads: DesktopRelease["linuxDownloads"] = null;
  if (compareVersions(version, "0.5.0") >= 0) {
    linuxDownloads = {} as NonNullable<DesktopRelease["linuxDownloads"]>;
    for (const arch of ["amd64", "arm64"] as const) {
      const image = `MachineControl_${version}_${arch}.AppImage`;
      const deb = `MachineControl_${version}_${arch}.deb`;
      linuxDownloads[arch] = { appimage: asset(image), deb: asset(deb) };
      asset(image + ".sig");
      asset(deb + ".sig");
      asset(`build-linux-${arch}.json`);
      asset(`payload-linux-${arch}.json`);
    }
  }
  return { version, url, downloads, windowsDownloads, linuxDownloads, manifestUrl: asset("latest.json") };
}
async function publicJson(
  url: string,
  fetcher: typeof fetch,
): Promise<unknown> {
  const response = await fetcher(url, {
    headers: {
      Accept: "application/json",
      "User-Agent": "machine-control-downloads",
    },
    signal: AbortSignal.timeout(8000),
    cf: { cacheTtl: 300, cacheEverything: true },
  });
  if (!response.ok) throw new Error("Release service unavailable");
  const text = await response.text();
  if (text.length > 2_000_000) throw new Error("Release metadata too large");
  return JSON.parse(text);
}
export async function loadDesktopRelease(
  fetcher: typeof fetch = fetch,
): Promise<DesktopRelease | null> {
  return selectDesktopRelease(
    await publicJson(
      `https://api.github.com/repos/${REPOSITORY}/releases?per_page=100`,
      fetcher,
    ),
  );
}
