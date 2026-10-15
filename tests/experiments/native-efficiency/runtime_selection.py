"""Select an exact installed runtime manifest without constructing vendor launchers.

Controller validation permits target-only absolute paths. Target validation reads
existing artifacts; it never executes a launcher, installs assets or edits consent.
All errors are structural and must not include manifest/environment contents.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import stat
import sys


class RuntimeConfigError(ValueError):
    pass


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def absolute_path(value, label):
    if (not isinstance(value, str) or not value or not Path(value).is_absolute() or
            any(marker in value for marker in ('${', '{{', '<', '>'))):
        raise RuntimeConfigError(label + ' must be an exact absolute target path; templates are unsupported')
    return Path(value)


def validate_bytes(raw, *, target_files=False):
    try:
        data = json.loads(raw)
        server = data['mcpServers']['cua_repl']
    except (ValueError, KeyError, TypeError, UnicodeError):
        raise RuntimeConfigError('Expected a JSON manifest containing mcpServers.cua_repl') from None
    if not isinstance(server, dict):
        raise RuntimeConfigError('cua_repl must be an MCP server object')
    if server.get('enabled') is False or server.get('disabled') is True:
        raise RuntimeConfigError('Disabled runtime templates are not executable launch configurations')
    command = absolute_path(server.get('command'), 'runtime command')
    args, env = server.get('args'), server.get('env')
    if not isinstance(args, list) or not args or not all(isinstance(arg, str) for arg in args):
        raise RuntimeConfigError('Runtime args must contain an exact installed launcher script')
    script = absolute_path(args[0], 'runtime launcher script')
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise RuntimeConfigError('Runtime env must contain string keys and values')
    repl = absolute_path(env.get('CUA_REPL_NODE_REPL_PATH'), 'node REPL artifact')
    service = absolute_path(env.get('SKY_CUA_SERVICE_PATH'), 'native service bundle')
    node = absolute_path(env['NODE_REPL_NODE_PATH'], 'node executable') if 'NODE_REPL_NODE_PATH' in env else None
    if target_files:
        for path, executable, label in [(command, True, 'runtime command'), (script, False, 'launcher script'),
                                        (repl, False, 'node REPL artifact'), (node, True, 'node executable')]:
            if path is not None and (not path.is_file() or executable and not os.access(path, os.X_OK)):
                raise RuntimeConfigError(label + ' is missing or not usable on target')
        try:
            info = plistlib.loads((service / 'Contents/Info.plist').read_bytes())
            executable = info['CFBundleExecutable']
            if not isinstance(executable, str) or Path(executable).name != executable or executable in ('.', '..'):
                raise ValueError()
            binary = service / 'Contents/MacOS' / executable
            if not binary.is_file() or not os.access(binary, os.X_OK):
                raise ValueError()
        except (OSError, ValueError, KeyError, TypeError, plistlib.InvalidFileException):
            raise RuntimeConfigError('Native service bundle metadata or executable is missing or invalid') from None
    return server


def private_input(path, checkout):
    """Read exact private bytes; target binaries need not exist on the controller."""
    path = Path(path).expanduser()
    try:
        mode = path.lstat().st_mode
        selected = path.resolve(strict=True)
        if not stat.S_ISREG(mode) or stat.S_IMODE(mode) != 0o600:
            raise RuntimeConfigError('runtime-config-file must be a regular mode-0600 file')
        checkout = Path(checkout).resolve()
        if selected == checkout or checkout in selected.parents:
            raise RuntimeConfigError('runtime-config-file must be private and outside checkout')
        raw = selected.read_bytes()
    except OSError:
        raise RuntimeConfigError('Private runtime-config-file is missing or unreadable') from None
    validate_bytes(raw)
    return raw, {'path': str(selected), 'sha256': digest_bytes(raw), 'mode': '0o600'}


def select_config(explicit=None, *, checkout, expected_sha256=None, private=False):
    if explicit is None:
        configs = list((Path.home() / '.codex/plugins/cache/openai-bundled/unified-computer-use').glob('*/.mcp.json'))
        if not configs:
            raise RuntimeConfigError('No cached runtime config found; supply --runtime-config-file explicitly')
        if len(configs) != 1:
            raise RuntimeConfigError('Multiple cached runtime configs are ambiguous; supply --runtime-config-file explicitly')
        selected = configs[0].resolve(strict=True)
        raw = selected.read_bytes()
        source = 'cache-exact-one'
    else:
        selected = Path(explicit).resolve(strict=True)
        if private:
            raw, _ = private_input(explicit, checkout)
        else:
            raw = selected.read_bytes()
        source = 'explicit-private' if private else 'selected-exact-path'
    if expected_sha256 and digest_bytes(raw) != expected_sha256:
        raise RuntimeConfigError('Selected runtime manifest changed from the supplied SHA-256')
    validate_bytes(raw, target_files=True)
    return selected, source


def receive(raw, *, checkout, expected_sha256):
    if digest_bytes(raw) != expected_sha256:
        raise RuntimeConfigError('Transferred runtime manifest SHA-256 mismatch')
    validate_bytes(raw, target_files=True)
    output = Path.home() / 'experiment/runtime-input'
    if output.resolve() == Path(checkout).resolve() or Path(checkout).resolve() in output.resolve().parents:
        raise RuntimeConfigError('Private runtime input must be outside checkout')
    os.umask(0o077)
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    destination = output / 'installed-mcp.json'
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
    if digest_bytes(destination.read_bytes()) != expected_sha256 or stat.S_IMODE(destination.stat().st_mode) != 0o600:
        raise RuntimeConfigError('Private runtime input persistence verification failed')
    return {'configPath': str(destination.resolve()), 'configSha256': expected_sha256,
            'mode': '0o600', 'directoryMode': oct(stat.S_IMODE(output.stat().st_mode))}


def fingerprint(explicit=None, *, checkout, expected_sha256=None, private=False):
    selected, source = select_config(explicit, checkout=checkout, expected_sha256=expected_sha256, private=private)
    from provenance import collect
    value = collect(selected)
    if expected_sha256 and value['configSha256'] != expected_sha256:
        raise RuntimeConfigError('Runtime manifest changed during fingerprint collection')
    value.update(configPath=str(selected), configSelection=source)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['receive', 'fingerprint'])
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--expected-sha256')
    parser.add_argument('--private', action='store_true')
    args = parser.parse_args()
    try:
        if args.operation == 'receive':
            if not args.expected_sha256:
                raise RuntimeConfigError('Receipt requires an expected manifest SHA-256')
            value = receive(sys.stdin.buffer.read(), checkout=args.checkout, expected_sha256=args.expected_sha256)
        else:
            value = fingerprint(args.config, checkout=args.checkout, expected_sha256=args.expected_sha256, private=args.private)
        print(json.dumps(value))
        return 0
    except Exception as error:
        print(json.dumps({'passed': False, 'stage': args.operation,
                          'errorCode': type(error).__name__,
                          'message': str(error) if isinstance(error, RuntimeConfigError) else
                          'Runtime selection or artifact fingerprint inspection failed'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
