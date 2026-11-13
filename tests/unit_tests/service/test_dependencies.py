from unittest.mock import Mock

import pytest
from fastapi import Request

from blueapi.service.routes.dependencies import get_passthrough_headers


@pytest.mark.parametrize(
    "headers, expected_headers",
    [
        ({}, {}),
        ({"foo": "bar"}, {}),
        ({"authorization": "yes"}, {"authorization": "yes"}),
        ({"autHORIzation": "yes"}, {"autHORIzation": "yes"}),
        ({"autHORIzation": "yes", "foo": "bar"}, {"autHORIzation": "yes"}),
        ({"autHORIzation": ""}, {"autHORIzation": ""}),
    ],
)
def test_get_passthrough_headers(
    headers: dict[str, str], expected_headers: dict[str, str]
):
    request = Mock(spec=Request)
    request.headers = headers
    assert get_passthrough_headers(request) == expected_headers
