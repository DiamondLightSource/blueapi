import re
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).parents[2]
ASYNCAPI_PATH = ROOT / "docs" / "reference" / "asyncapi.yaml"

EVENT_MODEL_TAG_URL = re.compile(
    r"https://raw\.githubusercontent\.com/bluesky/event-model/refs/tags/v([\d.]+)/"
)


def test_asyncapi_event_model_refs_match_pinned_version() -> None:
    expected_version = version("event-model")

    versions_found = set(EVENT_MODEL_TAG_URL.findall(ASYNCAPI_PATH.read_text()))

    assert versions_found, "No event-model schema references found in asyncapi.yaml"
    assert versions_found == {expected_version}, (
        f"asyncapi.yaml references event-model version(s) {versions_found}, "
        f"but pyproject.toml pins event-model=={expected_version}"
    )
