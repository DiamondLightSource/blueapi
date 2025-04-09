from collections.abc import Mapping
from pathlib import Path
from textwrap import dedent
from typing import Any
from unittest import mock
from unittest.mock import Mock, PropertyMock

import git
import pytest
import yaml
from deepdiff import DeepDiff
from semver import Version

from blueapi.config import ApplicationConfig
from blueapi.service.openapi import DOCS_SCHEMA_LOCATION, generate_schema

TOP = Path(__file__).parent.parent.parent.parent
MAIN = "main"


@pytest.fixture
def reference_schema() -> Mapping[str, Any]:
    repo = git.Repo(TOP)
    relative_path_to_schema = DOCS_SCHEMA_LOCATION.relative_to(TOP)
    raw_yaml = repo.git.show(f"{MAIN}:{relative_path_to_schema}")
    return yaml.safe_load(raw_yaml)


@mock.patch("blueapi.service.openapi.get_app")
def test_generate_schema(mock_get_app: Mock) -> None:
    mock_app = mock_get_app()

    from blueapi.service.main import get_app

    app = get_app(ApplicationConfig())

    title = PropertyMock(return_value="title")
    version = PropertyMock(return_value=app.version)
    openapi_version = PropertyMock(return_value=app.openapi_version)
    description = PropertyMock(return_value="description")
    routes = PropertyMock(return_value=[app.routes[0]])

    type(mock_app).title = title
    type(mock_app).version = version
    type(mock_app).openapi_version = openapi_version
    type(mock_app).description = description
    type(mock_app).routes = routes

    assert generate_schema() == {
        "openapi": openapi_version(),
        "info": {
            "title": title(),
            "description": description(),
            "version": version(),
        },
        "paths": {},
    }


@pytest.mark.skipif(
    not DOCS_SCHEMA_LOCATION.exists(),
    reason="If the schema file does not exist, the test is being run"
    " with a non-editable install",
)
def test_schema_updated() -> None:
    with DOCS_SCHEMA_LOCATION.open("r") as stream:
        docs_schema = yaml.safe_load(stream)
    assert DeepDiff(docs_schema, generate_schema()) == {}


@pytest.mark.skipif(
    not DOCS_SCHEMA_LOCATION.exists(),
    reason="If the schema file does not exist, the test is being run"
    " with a non-editable install",
)
def test_schema_version_bump_required(reference_schema: Mapping[str, Any]) -> None:
    current_version = _get_version(generate_schema(), "schema in working tree")
    main_version = _get_version(reference_schema, "schema in main")
    if reference_schema != generate_schema():
        assert current_version > main_version, dedent(f"""
        The REST API schema has changed compared to the main branch,
        meaning the API version needs to be updated too. For more details see
        https://diamondlightsource.github.io/blueapi/main/explanations/api-version.html.

        For a guide to deciding if the version change should be major, minor or patch
        see https://semver.org/

        If you do not think the API has changed, make sure you have the latest version
        of main locally in this repository:

        git fetch origin/main

        Current versions:
        main: {main_version}
        working tree: {current_version}
        """)


def _get_version(
    schema: Mapping[str, Any],
    description: str,
) -> Version:
    raw_version = schema.get("info", {}).get("version")
    assert raw_version is not None, f"info.version not found in {description}: {schema}"
    return Version.parse(raw_version)
