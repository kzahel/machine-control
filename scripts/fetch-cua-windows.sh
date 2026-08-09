#!/usr/bin/env bash
set -euo pipefail

runtime_id="${1:-}"
output_root="${2:-}"
case "$runtime_id" in
  win-x64)
    archive_name="cua-driver-rs-0.17.0-windows-x86_64-binary.zip"
    archive_sha="f7e366edc4b7148b4f6f78957782b2a2d962620b0daaeb99df7cf9dce6176193"
    executable_sha="635efe92eb0c3f9737db7e8aca0198f12ccf97e3269a9a75d28388690113db27"
    ;;
  win-arm64)
    archive_name="cua-driver-rs-0.17.0-windows-arm64-binary.zip"
    archive_sha="bd3febdabff06331efd0951495f34ef7a5fb2cc230fd5270bd34292bc7ee036a"
    executable_sha="fef346fc57fb57f5721ee77cf479c607cd5015580447cdca71a71ef43175afaa"
    ;;
  *)
    echo "usage: $0 win-arm64|win-x64 OUTPUT_ROOT" >&2
    exit 2
    ;;
esac
if [[ -z "$output_root" ]]; then
  echo "usage: $0 win-arm64|win-x64 OUTPUT_ROOT" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cache_root="$repo_root/.cache/providers/cua/0.17.0"
provider_root="$output_root/providers/cua"
archive_path="$cache_root/$archive_name"
release_root="https://github.com/trycua/cua/releases/download/cua-driver-rs-v0.17.0"
license_url="https://raw.githubusercontent.com/trycua/cua/d21e3447f9b08c761c090946648d5aca5e6c9cf1/LICENSE.md"
license_sha="c0779290c1d4783169aa3dbfb55feb505e563ef8a004bbf55298ceffcfbda8d9"

mkdir -p "$cache_root" "$provider_root"
if [[ ! -f "$archive_path" ]] ||
   [[ "$(shasum -a 256 "$archive_path" | awk '{print $1}')" != "$archive_sha" ]]; then
  curl -fsSL "$release_root/$archive_name" -o "$archive_path"
fi
actual_archive_sha="$(shasum -a 256 "$archive_path" | awk '{print $1}')"
if [[ "$actual_archive_sha" != "$archive_sha" ]]; then
  echo "Cua archive digest mismatch for $runtime_id" >&2
  exit 1
fi

unzip -j -o "$archive_path" cua-driver.exe -d "$provider_root" >/dev/null
actual_executable_sha="$(shasum -a 256 "$provider_root/cua-driver.exe" | awk '{print $1}')"
if [[ "$actual_executable_sha" != "$executable_sha" ]]; then
  echo "Cua executable digest mismatch for $runtime_id" >&2
  exit 1
fi

curl -fsSL "$license_url" -o "$provider_root/LICENSE.md"
actual_license_sha="$(shasum -a 256 "$provider_root/LICENSE.md" | awk '{print $1}')"
if [[ "$actual_license_sha" != "$license_sha" ]]; then
  echo "Cua license digest mismatch" >&2
  exit 1
fi
cp "$repo_root/providers/cua/provider.json" "$provider_root/provider.json"
