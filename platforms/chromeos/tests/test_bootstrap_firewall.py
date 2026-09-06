import shutil
"""Exercise generated firewall commands against an ordered rule fixture."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / "scripts/bootstrap.sh").read_text()
ALLOW = ["-p", "tcp", "--dport", "2223", "-j", "ACCEPT"]
DENY = ["-j", "REJECT"]
FAKE = r'''
import json, os, pathlib, sys
path = pathlib.Path(os.environ["FIREWALL_STATE"])
state = json.loads(path.read_text())
rules = state[pathlib.Path(sys.argv[0]).name]
args = [arg for arg in sys.argv[1:] if arg != "-w"]
action, chain, *rule = args
assert chain == "INPUT"
if action == "-I":
    position = int(rule.pop(0))
    rules.insert(position - 1, rule)
elif action == "-D":
    if rule not in rules:
        sys.exit(1)
    rules.remove(rule)
elif action == "-C":
    sys.exit(0 if rule in rules else 1)
else:
    raise AssertionError(action)
path.write_text(json.dumps(state))
'''


@unittest.skipIf(os.name == "nt" or not shutil.which("bash") or not shutil.which("ssh-keygen"), "Requires POSIX shell and OpenSSH")
class BootstrapFirewallTests(unittest.TestCase):
    def test_initial_and_repeated_bootstrap_put_allow_before_deny(self):
        fallback = SOURCE.split("cat > \"$SSH_DIR/start_sshd.sh\" << 'SCRIPT'\n", 1)[1].split("\nSCRIPT", 1)[0]
        fallback = fallback[fallback.index("while iptables -D"):fallback.index('\nif [ -r "$SSHD_PID"')]
        startup = SOURCE[SOURCE.index("  for cmd in iptables ip6tables; do"):]
        startup = startup.split("\n  done", 1)[0] + "\n  done\n"
        for script, commands in [(fallback, ["iptables"]), (startup, ["iptables", "ip6tables"])]:
            for copies in [0, 1, 2]:
                with self.subTest(commands=commands, existing_copies=copies), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    state = root / "state.json"
                    state.write_text(json.dumps({name: [DENY] + [ALLOW] * copies for name in commands}))
                    for name in commands:
                        executable = root / name
                        executable.write_text(f"#!{sys.executable}\n" + FAKE)
                        executable.chmod(0o755)
                    env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"], FIREWALL_STATE=str(state))
                    for _ in range(2):
                        subprocess.run(["bash", "-ec", script], env=env, check=True)
                        for rules in json.loads(state.read_text()).values():
                            self.assertEqual(rules, [ALLOW, DENY])
