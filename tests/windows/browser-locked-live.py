"""V2 locked Browser acceptance using the shared real-profile fixture.

Run only on a claimed appliance with a separately identified test browser.
The controller restores login/power after this actor leaves Windows locked.
Uses --install, --chrome, --output and optional --chromium; no legacy grants.
"""
import runpy
from pathlib import Path
import sys

if __name__ == "__main__":
    sys.argv.append("--locked-browser")
    runpy.run_path(str(Path(__file__).with_name("browser-profiles-live.py")), run_name="__main__")
