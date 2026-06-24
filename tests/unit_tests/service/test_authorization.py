from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import HttpUrl

from blueapi.config import OpaConfig
from blueapi.service.authorization import (
    OpaClient,
)

# Reusable client patch decorator
patch_client_session = patch(
    "blueapi.service.authorization.ClientSession",
    name="mock_client_session",
    spec=True,
)


@pytest.fixture(scope="module")
def opa_config() -> OpaConfig:
    return OpaConfig(
        root=HttpUrl("http://auth.example.com"),
    )


@patch_client_session
async def test_session_closed(session: MagicMock, opa_config: OpaConfig):
    async with OpaClient.for_config("p45", opa_config):
        pass
    session().close.assert_called_once()


@patch_client_session
async def test_opa_client_for_config(session: MagicMock, opa_config: OpaConfig):
    async with OpaClient.for_config("p45", opa_config) as opa:
        assert opa is not None
        session.assert_called_once_with(base_url="http://auth.example.com/")


@pytest.mark.parametrize("instrument", [None, "p99"])
async def test_opa_client_without_config(instrument: str | None):
    async with OpaClient.for_config(instrument, None) as opa:
        assert opa is None


async def test_opa_fails_without_instrument(opa_config: OpaConfig):
    with pytest.raises(ValueError, match="Instrument name is required"):
        OpaClient.for_config(None, opa_config)


@patch_client_session
async def test_opa_adds_input_fields(session: MagicMock, opa_config: OpaConfig):
    session.return_value.post = AsyncMock()
    async with OpaClient.for_config("p45", opa_config) as opa:
        assert opa is not None
        await opa._call_opa("foo/bar", data={"foo": "bar"})

    session.assert_called_once()
    session().post.assert_called_once_with(
        "foo/bar",
        json={"input": {"beamline": "p45", "audience": "account", "foo": "bar"}},
    )
