import subprocess
import sys

from blueapi import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "blueapi", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__
