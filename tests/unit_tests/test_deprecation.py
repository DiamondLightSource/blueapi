import pytest


# https://github.com/DiamondLightSource/blueapi/issues/1256
def test_invalid_parameters_deprecated():
    with pytest.deprecated_call():
        from blueapi.client.rest import InvalidParameters  # noqa


# https://github.com/DiamondLightSource/blueapi/issues/1256
def test_no_content_deprecated():
    with pytest.deprecated_call():
        from blueapi.client.rest import NoContent  # noqa


# https://github.com/DiamondLightSource/blueapi/issues/1256
def test_unauthorised_access_deprecated():
    with pytest.deprecated_call():
        from blueapi.client.rest import UnauthorisedAccess  # noqa


# https://github.com/DiamondLightSource/blueapi/issues/1256
def test_unknown_plan_deprecated():
    with pytest.deprecated_call():
        from blueapi.client.rest import UnknownPlan  # noqa


# https://github.com/DiamondLightSource/blueapi/issues/1256
def test_missing_stomp_deprecated():
    with pytest.deprecated_call():
        from blueapi.config import MissingStompConfiguration  # noqa
