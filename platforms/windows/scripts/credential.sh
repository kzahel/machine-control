#!/usr/bin/env bash

# Keep the appliance's login password recoverable. The current password always
# lives in WINVM_LOGIN_SECRET_FILE (mode 0600). A rotation writes the new
# password to a pending file before changing Windows, so no outcome can leave
# the appliance with a password that is not stored. Secrets travel only on
# standard input; never in arguments, environment variables, or output.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly PROVIDER="$WINVM_REPO_DIR/providers/$WINVM_PROVIDER/provider.sh"

usage() {
    cat <<'USAGE'
Usage: winvm credential status [--json]
       winvm credential store FILE     Record the current password from FILE
       winvm credential rotate         Set and store a new random password
       winvm credential verify         Check the stored password in the guest
       winvm login                     Sign in with the stored password
USAGE
}

secret_file_ready() {
    [[ -f "$WINVM_LOGIN_SECRET_FILE" && -s "$WINVM_LOGIN_SECRET_FILE" &&
       "$(stat -c %a "$WINVM_LOGIN_SECRET_FILE" 2>/dev/null ||
          stat -f %Lp "$WINVM_LOGIN_SECRET_FILE")" == 600 ]]
}

require_pinned() {
    if [[ -z "$WINVM_EXPECTED_UTM_ID" ]]; then
        printf 'The appliance identity is unpinned; pin it before storing credentials.\n' >&2
        return 1
    fi
}

prepare_directory() {
    local directory
    directory="$(dirname "$WINVM_LOGIN_SECRET_FILE")"
    mkdir -p "$directory"
    chmod 700 "$directory"
}

credential_status() {
    local state=missing pending=false
    secret_file_ready && state=stored
    [[ -e "$WINVM_LOGIN_SECRET_FILE.pending" ]] && pending=true
    if [[ "${1:-}" == --json ]]; then
        jq -n --arg state "$state" --argjson pending "$pending" \
            '{schema:"winvm-credential-status/v0",loginPassword:$state,
              rotationPending:$pending}'
    else
        printf 'login password: %s; rotation pending: %s\n' "$state" "$pending"
    fi
}

credential_store() {
    local source="${1:-}" staged
    if [[ -z "$source" || ! -f "$source" || ! -s "$source" ]]; then
        printf 'Usage: winvm credential store FILE\n' >&2
        return 2
    fi
    require_pinned
    prepare_directory
    staged="$(mktemp "$WINVM_LOGIN_SECRET_FILE.XXXXXX")"
    chmod 600 "$staged"
    # Store exactly one line without a trailing newline.
    tr -d '\r\n' <"$source" >"$staged"
    mv -f "$staged" "$WINVM_LOGIN_SECRET_FILE"
    printf 'login password stored\n'
}

# Run a PowerShell script in the guest with the secret on standard input.
# EncodedCommand keeps the script intact through the guest's SSH shell.
guest_with_secret() {
    local script="$1" secret_file="$2" encoded
    encoded="$(python3 -c 'import base64, sys
print(base64.b64encode(sys.argv[1].encode("utf-16-le")).decode())' \
        "\$ProgressPreference = 'SilentlyContinue'; $script")"
    "$PROVIDER" ssh-exec powershell.exe -NoLogo -NoProfile -NonInteractive \
        -EncodedCommand "$encoded" <"$secret_file" 2>/dev/null | tr -d '\r'
}

readonly VALIDATE_SCRIPT='Add-Type -AssemblyName System.DirectoryServices.AccountManagement; $p = [Console]::In.ReadLine(); $c = New-Object System.DirectoryServices.AccountManagement.PrincipalContext([System.DirectoryServices.AccountManagement.ContextType]::Machine); if ($c.ValidateCredentials($env:USERNAME, $p)) { "valid" } else { "invalid" }'
readonly SET_SCRIPT='$p = [Console]::In.ReadLine(); Set-LocalUser -Name $env:USERNAME -Password (ConvertTo-SecureString $p -AsPlainText -Force); "rotated"'

credential_verify() {
    if ! secret_file_ready; then
        printf 'No stored login password for this appliance.\n' >&2
        return 1
    fi
    if [[ "$(guest_with_secret "$VALIDATE_SCRIPT" "$WINVM_LOGIN_SECRET_FILE")" != valid ]]; then
        printf 'The stored login password was not accepted by Windows.\n' >&2
        return 1
    fi
    printf 'stored login password verified\n'
}

credential_rotate() {
    local pending="$WINVM_LOGIN_SECRET_FILE.pending"
    require_pinned
    if [[ -e "$pending" ]]; then
        printf '%s\n' \
            'A previous rotation did not finish; its password is in the pending' \
            'file. Verify which password Windows accepts before retrying.' >&2
        return 1
    fi
    prepare_directory
    (umask 077 && python3 -c '
import secrets, string
alphabet = string.ascii_letters + string.digits
print("Mc" + "".join(secrets.choice(alphabet) for _ in range(20)) + "-7", end="")
' >"$pending")
    chmod 600 "$pending"
    guest_with_secret "$SET_SCRIPT" "$pending" >/dev/null || true
    if [[ "$(guest_with_secret "$VALIDATE_SCRIPT" "$pending")" != valid ]]; then
        if [[ "$(guest_with_secret "$VALIDATE_SCRIPT" "$WINVM_LOGIN_SECRET_FILE")" == valid ]]; then
            rm -f "$pending"
            printf 'Windows did not apply the new password; the stored one is unchanged.\n' >&2
        else
            printf '%s\n' \
                'Windows accepted neither password; both files are kept for recovery.' >&2
        fi
        return 1
    fi
    mv -f "$pending" "$WINVM_LOGIN_SECRET_FILE"
    printf 'login password rotated, verified, and stored\n'
}

login() {
    if ! secret_file_ready; then
        printf 'No stored login password for this appliance: %s\n' \
            "$WINVM_LOGIN_SECRET_FILE" >&2
        return 1
    fi
    "$WINVM_REPO_DIR/../../scripts/login-windows.sh" "$WINVM_SSH_HOST" password \
        <"$WINVM_LOGIN_SECRET_FILE"
}

command="${1:-}"
[[ $# -gt 0 ]] && shift
case "$command" in
    status) credential_status "$@" ;;
    store) credential_store "$@" ;;
    rotate) credential_rotate "$@" ;;
    verify) credential_verify "$@" ;;
    login) login "$@" ;;
    *) usage >&2; exit 2 ;;
esac
