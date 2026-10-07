import time
from contextlib import AbstractContextManager, nullcontext
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import jwt
import pytest
from fastapi import HTTPException
from pydantic import HttpUrl

from blueapi.config import OIDCConfig, OpaConfig, ServiceAccount
from blueapi.service.authorization import (
    OpaClient,
    OpaUserClient,
    opa,
    require_tiled_service_account,
    submit_permission,
    validate_tiled_config,
)
from blueapi.service.model import TaskRequest

ISSUER = "https://auth.example.com/realms/master"

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
    )


@patch_client_session
async def test_exception_raised_when_opa_fails(
    session: MagicMock, opa_config: OpaConfig
):
    session.return_value.post = AsyncMock(side_effect=RuntimeError("Connection failed"))
    async with OpaClient.for_config("p45", opa_config) as client:
        assert client is not None
        with pytest.raises(RuntimeError, match="Connection failed"):
            await client.is_admin(token="foo_bar")


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
        json={"input": {"instrument": "p45", "audience": "account", "foo": "bar"}},
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
                "instrument": "p99",
                "audience": "account",
                "instrument_session": 1,
                "proposal_category": "CM",
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
        json={
            "input": {"token": "foo_bar", "instrument": "p45", "audience": "account"}
        },
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


@pytest.fixture
def tiled_oidc() -> OIDCConfig:
    oidc = Mock(spec=OIDCConfig)
    oidc.token_endpoint = "token-endpoint"
    oidc.jwks_uri = "https://example.com/certs"
    oidc.issuer = ISSUER
    oidc.id_token_signing_alg_values_supported = ["RS256"]
    return oidc


def tiled_token(rsa_private_key: str, **claims) -> str:
    now = time.time()
    return jwt.encode(
        {"iss": ISSUER, "exp": now + 900, "iat": now, **claims},
        key=rsa_private_key,
        algorithm="RS256",
        headers={"kid": "secret"},
    )


SERVICE_ACCOUNT = {"aud": ["tiled_writer_raw", "account"], "instrument": "p99"}


def test_require_tiled_service_account(
    rsa_private_key: str, mock_jwks_fetch, tiled_oidc: OIDCConfig
):
    with mock_jwks_fetch:
        require_tiled_service_account(
            tiled_token(rsa_private_key, **SERVICE_ACCOUNT), tiled_oidc, "p99"
        )


@pytest.mark.parametrize(
    "claims,match",
    [
        ({**SERVICE_ACCOUNT, "instrument": "p45"}, "not valid for 'p99'"),
        ({"aud": ["tiled_writer_raw"]}, "not valid for 'p99'"),
        ({**SERVICE_ACCOUNT, "fedid": "abc123"}, "not valid for 'p99'"),
        ({**SERVICE_ACCOUNT, "aud": "account"}, "token is not valid"),
        ({**SERVICE_ACCOUNT, "iss": "https://other.example.com"}, "token is not valid"),
        ({**SERVICE_ACCOUNT, "exp": time.time() - 10}, "token is not valid"),
    ],
)
def test_require_tiled_service_account_rejected(
    rsa_private_key: str,
    mock_jwks_fetch,
    tiled_oidc: OIDCConfig,
    claims: dict,
    match: str,
):
    with mock_jwks_fetch, pytest.raises(ValueError, match=match):
        require_tiled_service_account(
            tiled_token(rsa_private_key, **claims), tiled_oidc, "p99"
        )


async def test_validate_tiled_config(tiled_oidc: OIDCConfig):
    tiled = ServiceAccount()
    with (
        patch("blueapi.service.authorization.TiledAuth") as auth,
        patch("blueapi.service.authorization.require_tiled_service_account") as check,
    ):
        auth.return_value.get_access_token.return_value = "tiled-token"
        await validate_tiled_config(tiled, tiled_oidc, "p99")

    auth.assert_called_once_with(tiled)
    check.assert_called_once_with("tiled-token", tiled_oidc, "p99")


@pytest.mark.parametrize(
    "tiled_auth,oidc,instrument",
    [
        (None, None, "p99"),
        (
            None,
            OIDCConfig(well_known_url="http://example.com", client_id="test-client"),
            "p99",
        ),
        ("api_key", None, "p99"),
        (
            "api_key",
            OIDCConfig(well_known_url="http://example.com", client_id="test-client"),
            "p99",
        ),
        (ServiceAccount(), None, "p99"),
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
    instrument: str | None,
):
    with patch("blueapi.service.authorization.require_tiled_service_account") as check:
        assert await validate_tiled_config(tiled_auth, oidc, instrument) is None
    check.assert_not_called()


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
