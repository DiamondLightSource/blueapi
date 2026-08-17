from contextlib import AbstractContextManager, nullcontext
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException
from pydantic import HttpUrl

from blueapi.config import OIDCConfig, OpaConfig, ServiceAccount
from blueapi.service.authorization import (
    OpaClient,
    OpaUserClient,
    opa,
    submit_permission,
    validate_tiled_config,
)
from blueapi.service.model import TaskRequest

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
        submit_task_check="/auth/submit",
        admin_check="/auth/admin",
        tiled_service_account_check="/auth/tiled",
    )


@patch_client_session
@pytest.mark.parametrize(
    "result,context",
    [
        (False, pytest.raises(ValueError, match="Tiled service account is not valid ")),
        (True, nullcontext()),
    ],
)
async def test_tiled_service_account(
    session: MagicMock,
    opa_config: OpaConfig,
    result: bool,
    context: AbstractContextManager,
):
    session.return_value.post = AsyncMock(
        return_value=MagicMock(json=AsyncMock(return_value={"result": result}))
    )

    client = OpaClient(instrument="p99", config=opa_config)

    session.assert_called_once_with(base_url="http://auth.example.com/")
    with context:
        await client.require_tiled_service_account(token="foo_bar")
    session().post.assert_called_once_with(
        "/auth/tiled",
        json={"input": {"token": "foo_bar", "beamline": "p99", "audience": "account"}},
    )


@patch_client_session
async def test_exception_raised_when_opa_fails(
    session: MagicMock, opa_config: OpaConfig
):
    session.return_value.post = AsyncMock(side_effect=RuntimeError("Connection failed"))
    async with OpaClient.for_config("p45", opa_config) as client:
        assert client is not None
        with pytest.raises(RuntimeError, match="Connection failed"):
            await client.require_tiled_service_account(token="foo_bar")


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


@pytest.mark.parametrize(
    "result,context",
    [(True, nullcontext()), (False, pytest.raises(HTTPException, match="403"))],
)
@patch_client_session
async def test_require_submit_task(
    session: MagicMock,
    opa_config: OpaConfig,
    result: bool,
    context: AbstractContextManager,
):
    session.return_value.post = AsyncMock(
        return_value=MagicMock(json=AsyncMock(return_value={"result": result}))
    )

    client = OpaClient(instrument="p99", config=opa_config)

    session.assert_called_once_with(base_url="http://auth.example.com/")
    with context:
        await client.require_submit_task(
            instrument_session="cm12345-1", token="foo_bar"
        )

    session().post.assert_called_once_with(
        "/auth/submit",
        json={
            "input": {
                "token": "foo_bar",
                "beamline": "p99",
                "audience": "account",
                "visit": 1,
                "proposal": 12345,
            }
        },
    )


@patch_client_session
async def test_opa_require_submit_task_invalid_session(
    session: MagicMock, opa_config: OpaConfig
):
    client = OpaClient(instrument="p45", config=opa_config)

    with pytest.raises(ValueError, match="Invalid instrument session"):
        await client.require_submit_task(
            instrument_session="not a session", token="foo_bar"
        )


@pytest.mark.parametrize("result", [True, False])
@patch_client_session
async def test_opa_is_admin(session: MagicMock, opa_config: OpaConfig, result: bool):
    session.return_value.post = AsyncMock(
        return_value=MagicMock(json=AsyncMock(return_value={"result": result}))
    )
    client = OpaClient(instrument="p45", config=opa_config)

    admin = await client.is_admin("foo_bar")

    assert admin == result

    session().post.assert_called_once_with(
        "/auth/admin",
        json={"input": {"token": "foo_bar", "beamline": "p45", "audience": "account"}},
    )


@pytest.mark.parametrize(
    "result,context",
    [
        (None, nullcontext()),
        (HTTPException(status_code=403), pytest.raises(HTTPException, match="403")),
    ],
)
async def test_user_client_can_submit_task(result, context: AbstractContextManager):
    opa = MagicMock(spec=OpaUserClient)
    opa.require_submit_task = AsyncMock(side_effect=result)

    user_client = OpaUserClient(opa, "foo_bar")

    with context:
        await user_client.can_submit_task(
            TaskRequest(name="foo", params={}, instrument_session="cm12345-1")
        )
    opa.require_submit_task.assert_called_once_with("cm12345-1", "foo_bar")


@pytest.mark.parametrize("result", [True, False])
async def test_user_client_admin(result: bool):
    opa = MagicMock(spec=OpaUserClient)
    opa.is_admin = AsyncMock(return_value=result)

    user_client = OpaUserClient(opa, "foo_bar")

    admin = await user_client.admin()

    assert admin == result


async def test_validate_tiled_config():
    opa = MagicMock(spec=OpaClient)
    tiled = ServiceAccount()
    oidc = Mock(spec=OIDCConfig)
    oidc.token_endpoint = "token-endpoint"
    with patch("blueapi.service.authorization.TiledAuth") as auth:
        auth.return_value.get_access_token.return_value = "tiled-token"
        await validate_tiled_config(tiled, oidc, opa)

    auth.assert_called_once_with(tiled)
    opa.require_tiled_service_account.assert_called_once_with("tiled-token")


@pytest.mark.parametrize(
    "tiled_auth,oidc,opa_client",
    [
        (None, None, MagicMock(spec=OpaClient)),
        (
            None,
            OIDCConfig(well_known_url="http://example.com", client_id="test-client"),
            MagicMock(spec=OpaClient),
        ),
        ("api_key", None, MagicMock(spec=OpaClient)),
        (
            "api_key",
            OIDCConfig(well_known_url="http://example.com", client_id="test-client"),
            MagicMock(spec=OpaClient),
        ),
        (ServiceAccount(), None, MagicMock(spec=OpaClient)),
        (
            ServiceAccount(),
            OIDCConfig(well_known_url="http://example.com", client_id="test-client"),
            None,
        ),
    ],
)
async def test_validate_tiled_config_with_missing_config(
    tiled_auth: ServiceAccount | str | None,
    oidc: OIDCConfig | None,
    opa_client: MagicMock | None,
):
    assert await validate_tiled_config(tiled_auth, oidc, opa_client) is None
    if opa_client is not None:
        opa_client.require_tiled_service_account.assert_not_called()


async def test_opa_dependency_method():
    request = MagicMock()

    user_client = await opa(request, "foo_bar")

    assert user_client is not None
    assert user_client.client == request.app.state.authz
    assert user_client.token == "foo_bar"


async def test_opa_dependency_without_token():
    request = MagicMock()

    with pytest.raises(HTTPException, match="401"):
        await opa(request, None)


@pytest.mark.parametrize("token", ["foo_bar", None])
async def test_opa_dependency_without_authz(token):
    request = MagicMock()
    del request.app.state.authz
    user_client = await opa(request, token)
    assert user_client is None


@pytest.mark.parametrize(
    "result,context",
    [
        (None, nullcontext()),
        (HTTPException(status_code=403), pytest.raises(HTTPException, match="403")),
    ],
)
async def test_submit_permission_dependency(result, context: AbstractContextManager):
    opa = MagicMock(spec=OpaUserClient)
    opa.can_submit_task.side_effect = result
    with context:
        await submit_permission(opa, Mock())


async def test_submit_permission_dependency_without_opa():
    assert await submit_permission(None, Mock()) is None
