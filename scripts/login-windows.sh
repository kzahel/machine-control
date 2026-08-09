#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <ssh-target> pin|password" >&2
  exit 2
fi

ssh_target="$1"
credential_kind="$2"
case "$credential_kind" in
  pin|password) ;;
  *) echo "credential kind must be pin or password" >&2; exit 2 ;;
esac

secret=""
cleanup() {
  secret=""
  unset secret
}
trap cleanup EXIT HUP INT TERM

printf 'Enter Windows %s: ' "$credential_kind" >&2
if ! IFS= read -r -s secret; then
  printf '\nUnable to read credential\n' >&2
  exit 1
fi
printf '\n' >&2
if [[ -z "$secret" ]]; then
  echo "credential must not be empty" >&2
  exit 2
fi

remote_command="C:\\ProgramData\\MachineControl\\runtime\\machine-control-windows.exe login --kind $credential_kind"
printf '%s' "$secret" | ssh -T -- "$ssh_target" "$remote_command"
