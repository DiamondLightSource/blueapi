from unittest import mock
from unittest.mock import Mock, PropertyMock

import pytest
import yaml

from blueapi.service.openapi import DOCS_SCHEMA_LOCATION, generate_schema


@mock.patch("blueapi.service.openapi.get_app")
def test_generate_schema(mock_get_app: Mock) -> None:
    mock_app = mock_get_app()

    from blueapi.service.main import get_app

    app = get_app()

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

    assert docs_schema == generate_schema()
