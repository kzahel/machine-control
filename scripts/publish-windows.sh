#!/usr/bin/env bash
set -euo pipefail

runtime_id="${1:-win-arm64}"
case "$runtime_id" in
  win-arm64|win-x64) ;;
  *) echo "usage: $0 win-arm64|win-x64" >&2; exit 2 ;;
esac

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
publish_parent="$repo_root/publish"
publish_root="$publish_parent/$runtime_id"

if ! command -v dotnet >/dev/null 2>&1; then
  printf 'The .NET SDK is required to publish Windows packages.\n' >&2
  exit 1
fi
sdk_version="$(dotnet --version)"
sdk_base="$(dotnet --list-sdks | awk -v version="$sdk_version" '
  $1 == version {
    value = $0
    sub(/^[^[]*\[/, "", value)
    sub(/\].*$/, "", value)
    print value
    exit
  }
')"
windows_desktop_targets="$sdk_base/$sdk_version/Sdks/Microsoft.NET.Sdk.WindowsDesktop/targets/Microsoft.NET.Sdk.WindowsDesktop.targets"
if [[ -z "$sdk_base" || ! -f "$windows_desktop_targets" ]]; then
  printf '%s\n' \
    'The selected .NET SDK lacks WindowsDesktop cross-publish targets.' \
    'Install the full Microsoft .NET SDK and select it on PATH.' >&2
  exit 1
fi

mkdir -p "$publish_parent"
staged_root="$(mktemp -d "$publish_parent/.$runtime_id.XXXXXX")"
cleanup() {
  if [[ -d "$staged_root" &&
        "$staged_root" == "$publish_parent/.$runtime_id."* ]]; then
    rm -rf -- "$staged_root"
  fi
}
trap cleanup EXIT INT TERM

dotnet publish \
  "$repo_root/src/MachineControl.Windows/MachineControl.Windows.csproj" \
  --configuration Release \
  --runtime "$runtime_id" \
  --self-contained true \
  --output "$staged_root"

"$repo_root/scripts/fetch-cua-windows.sh" \
  "$runtime_id" \
  "$staged_root"

for fixture in MachineControl.Fixture MachineControl.ElevatedFixture; do
  dotnet publish \
    "$repo_root/src/$fixture/$fixture.csproj" \
    --configuration Release \
    --runtime "$runtime_id" \
    --self-contained true \
    --output "$staged_root/fixtures"
done

mkdir -p "$staged_root/support"
cp -- \
  "$repo_root/platforms/windows/guests/windows/post-update.ps1" \
  "$repo_root/platforms/windows/guests/windows/bootstrap-development.ps1" \
  "$staged_root/support/"

if [[ "$publish_root" != "$publish_parent/$runtime_id" ]]; then
  printf 'Refusing unexpected publish path: %s\n' "$publish_root" >&2
  exit 1
fi
rm -rf -- "$publish_root"
mv -- "$staged_root" "$publish_root"
trap - EXIT INT TERM
