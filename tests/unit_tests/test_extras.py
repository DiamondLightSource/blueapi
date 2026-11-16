import subprocess
import sys

SERVER_ONLY = ["ophyd_async", "git", "tiled", "aioca", "dodal", "graypy"]


def _run(blocked: list[str], code: str) -> subprocess.CompletedProcess[str]:
    # A None entry in sys.modules makes the import fail as if it was not installed
    setup = f"import sys; sys.modules.update(dict.fromkeys({blocked}));"
    return subprocess.run(
        [sys.executable, "-c", setup + code], capture_output=True, text=True
    )


def test_client_imports_without_server_dependencies():
    result = _run(SERVER_ONLY, "import blueapi.__main__, blueapi.client")
    assert result.returncode == 0, result.stderr


def test_client_commands_ask_for_client_extra():
    result = _run(
        ["websockets"],
        "from blueapi.__main__ import main; main(['controller', 'plans'])",
    )
    assert result.returncode != 0
    assert "pip install blueapi[client]" in result.stderr
