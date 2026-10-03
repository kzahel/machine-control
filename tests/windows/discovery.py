"""Installed Windows EXE/pipe/identity acceptance; no system Python in child PATH.

Run with a harness Python in the interactive session for --launch. Offline mode
also works in session 0. All artifacts are confined to a temporary directory.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", type=Path, required=True)
    parser.add_argument("--launch", action="store_true",
                        help="Explicitly ensure the desktop app is running; caller owns cleanup")
    args = parser.parse_args()
    root = args.install.resolve(strict=True)
    exe = root / "machine-control.exe"
    legacy = root / "mc-cli/commands/machine-control.cmd"
    receipt = json.loads((root / "mc-cli/client-runtime.json").read_text())
    environment = dict(os.environ, PATH=os.path.join(os.environ["SystemRoot"], "System32"),
                       PYTHONHOME="missing-runtime", PYTHONPATH="missing-modules")
    environment.pop("MACHINE_CONTROL_CLI_LAUNCHER", None)
    with tempfile.TemporaryDirectory(prefix="mc discovery ") as temp:
        def run(command, expected=0, **kwargs):
            result = subprocess.run(command, cwd=temp, env=environment, timeout=25,
                                    capture_output=True, text=True, encoding="utf-8", **kwargs)
            assert result.returncode == expected, (command, result.returncode, result.stderr)
            return result

        assert "agent" in run([str(exe), "--help"]).stdout
        assert "claim release" in run([str(exe), "agent", "instructions"]).stdout
        assert json.loads(run([str(exe), "agent", "identity"]).stdout) == receipt
        details = json.loads(run([str(exe), "agent", "identity", "--paths"]).stdout)
        assert Path(details["paths"]["launcher"]) == exe
        assert Path(details["paths"]["installationRoot"]) == root
        assert Path(details["paths"]["interpreter"]) == root / "mc-cli/python/python.exe"
        invalid = subprocess.run([str(exe), "not-a-command", 'spaces "quotes" Ω & %PATH%'],
                                 cwd=temp, env=environment, capture_output=True,
                                 encoding="utf-8", timeout=25)
        assert invalid.returncode != 0
        # Batch cmd waits for GUI executables; verify its output and exit status.
        batch = Path(temp) / "probe.cmd"
        batch.write_text(f'@echo off\r\n"{exe}" agent identity\r\nexit /b %errorlevel%\r\n')
        assert json.loads(run([os.environ["COMSPEC"], "/d", "/c", str(batch)]).stdout) == receipt
        ps = "& '" + str(exe).replace("'", "''") + "' agent identity | Out-String; exit $LASTEXITCODE"
        assert json.loads(run(["powershell.exe", "-NoProfile", "-Command", ps]).stdout) == receipt
        with (Path(temp) / "identity.json").open("wb") as output:
            result = subprocess.run([str(exe), "agent", "identity"], stdout=output,
                                    stderr=subprocess.PIPE, env=environment, timeout=25)
        assert result.returncode == 0
        assert json.loads((Path(temp) / "identity.json").read_text()) == receipt
        timing = {}
        for name, command in [("exe", [str(exe)]),
                              ("cmd", [os.environ["COMSPEC"], "/d", "/c", str(legacy)])]:
            samples = []
            for _ in range(10):
                start = time.perf_counter()
                assert json.loads(run([*command, "agent", "identity"]).stdout) == receipt
                samples.append(round((time.perf_counter() - start) * 1000, 2))
            timing[name] = {"firstMs": samples[0], "warmMedianMs": statistics.median(samples[1:]),
                            "samplesMs": samples}
        if args.launch:
            first = run([str(exe)])
            assert "Machine Control is running" in first.stdout
            assert "agent instructions" in first.stdout
            assert "Machine Control is running" in run([str(exe)]).stdout
            assert "Machine Control is running" in run([str(exe), "--start"]).stdout
        print(json.dumps({"passed": True, "launchTested": args.launch, "timing": timing}))


if __name__ == "__main__":
    main()
