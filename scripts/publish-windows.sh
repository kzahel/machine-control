#!/usr/bin/env bash
set -euo pipefail

runtime_id="${1:-win-arm64}"
case "$runtime_id" in
  win-arm64|win-x64) ;;
  *) echo "usage: $0 win-arm64|win-x64" >&2; exit 2 ;;
esac

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
dotnet publish \
  "$repo_root/src/MachineControl.Windows/MachineControl.Windows.csproj" \
  --configuration Release \
  --runtime "$runtime_id" \
  --self-contained true \
  --output "$repo_root/publish/$runtime_id"

for fixture in MachineControl.Fixture MachineControl.ElevatedFixture; do
  dotnet publish \
    "$repo_root/src/$fixture/$fixture.csproj" \
    --configuration Release \
    --runtime "$runtime_id" \
    --self-contained true \
    --output "$repo_root/publish/$runtime_id/fixtures"
done
