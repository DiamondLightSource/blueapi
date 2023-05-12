# this should test if we change app, what openapi is generated.

import json

# i.e.checking that the openapi generation actually works.
from pathlib import Path

import mock
from mock import Mock, PropertyMock


@mock.patch("blueapi.service.openapi.app")
def test_init(mock_app: Mock):
    from blueapi.service.main import app

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

    from blueapi.service import openapi

    with mock.patch.object(openapi, "__name__", "__main__"):
        location = Path(__file__).parent / "test_file.json"
        openapi.init(location)
        print("ah")

        with open(location, "r") as f:
            result = json.load(f)

        assert result == {
            "openapi": openapi_version(),
            "info": {
                "title": title(),
                "description": description(),
                "version": version(),
            },
            "paths": {},
        }

    location.unlink()
