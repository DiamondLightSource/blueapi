# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mantelo==2.2.1",
# ]
# ///
"""Configure the local Keycloak instance used by the system tests."""

import os
from collections.abc import Callable
from functools import wraps
from typing import Any

from mantelo import KeycloakAdmin

SERVER = os.environ.get("KEYCLOAK_SERVER")
REALM = os.environ.get("KEYCLOAK_REALM")
ADMIN_USERNAME = os.environ.get("KC_BOOTSTRAP_ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("KC_BOOTSTRAP_ADMIN_PASSWORD")

USERS = {"alice": "alice", "bob": "bob"}

admin = KeycloakAdmin.from_username_password(
    server_url=SERVER,
    realm_name=REALM,
    client_id="admin-cli",
    username=ADMIN_USERNAME,
    password=ADMIN_PASSWORD,
)


def protocol_mapper(
    name: str, mapper_type: str, config: dict[str, str]
) -> dict[str, Any]:
    return {
        "name": name,
        "protocol": "openid-connect",
        "protocolMapper": mapper_type,
        "consentRequired": False,
        "config": config,
    }


def audience_mapper(
    audience: str,
    name: str = "audience-mapper",
    extra_config: dict[str, str] | None = None,
) -> dict[str, Any]:
    return protocol_mapper(
        name,
        "oidc-audience-mapper",
        {
            "introspection.token.claim": "true",
            "access.token.claim": "true",
            "included.custom.audience": audience,
            **(extra_config or {}),
        },
    )


def hardcoded_claim_mapper(
    name: str, claim_value: str, extra_config: dict[str, str] | None = None
) -> dict[str, Any]:
    return protocol_mapper(
        name,
        "oidc-hardcoded-claim-mapper",
        {
            "introspection.token.claim": "true",
            "claim.value": claim_value,
            "userinfo.token.claim": "true",
            "id.token.claim": "true",
            "access.token.claim": "true",
            "claim.name": name,
            "jsonType.label": "String",
            **(extra_config or {}),
        },
    )


def general_mappers(audience: str) -> dict[str, Any]:
    return {
        "protocolMappers": [
            protocol_mapper(
                "username",
                "oidc-usermodel-attribute-mapper",
                {
                    "aggregate.attrs": "false",
                    "introspection.token.claim": "true",
                    "multivalued": "false",
                    "userinfo.token.claim": "true",
                    "user.attribute": "username",
                    "id.token.claim": "true",
                    "lightweight.claim": "false",
                    "access.token.claim": "true",
                    "claim.name": "fedid",
                    "jsonType.label": "String",
                },
            ),
            audience_mapper(audience),
        ]
    }


def beamline_service_account_mappers() -> dict[str, Any]:
    return {
        "protocolMappers": [
            hardcoded_claim_mapper(
                "beamline",
                "adsim",
                extra_config={
                    "lightweight.claim": "false",
                    "access.tokenResponse.claim": "false",
                },
            ),
            audience_mapper(
                "tiled-writer",
                name="tiled",
                extra_config={"id.token.claim": "false", "lightweight.claim": "false"},
            ),
        ]
    }


def user_service_account_mappers(audience: str, fedid: str) -> dict[str, Any]:
    return {
        "protocolMappers": [
            hardcoded_claim_mapper("fedid", fedid),
            audience_mapper(audience),
        ]
    }


def cleanup_components() -> None:
    for component_type in ("Allowed Protocol Mapper Types", "Allowed Client Scopes"):
        for component in admin.components.get(name=component_type):
            admin.components(component["id"]).delete()


def create_users() -> None:
    for username, password in USERS.items():
        response, _ = admin.users.as_raw().post({"username": username, "enabled": True})
        user_id = response.headers["Location"].rsplit("/", 1)[-1]
        admin.users(user_id).reset_password.put(
            {"type": "password", "value": password, "temporary": False}
        )
        print(f"User '{username}' created successfully.")


def create_client(
    build_payload: Callable[..., dict[str, Any]],
) -> Callable[..., None]:
    """Wrap a payload builder with the shared create-if-absent flow."""

    @wraps(build_payload)
    def wrapper(client_id: str, **kwargs: Any) -> None:
        if admin.clients.get(clientId=client_id):
            print(f">> Skipping {client_id} (exists)")
            return

        print(f">> Creating {client_id}...")
        payload = build_payload(**kwargs)
        payload["clientId"] = client_id
        admin.clients.post(payload)

    return wrapper


@create_client
def create_cli_client(
    aud: str = "",
    attributes: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload = general_mappers(aud)
    payload.update(
        standardFlowEnabled=False,
        publicClient=True,
        redirectUris=["/*"],
        attributes={
            "frontchannel.logout.session.required": "true",
            "oauth2.device.authorization.grant.enabled": "true",
            "use.refresh.tokens": "true",
            "backchannel.logout.session.required": "true",
        },
    )
    return payload


@create_client
def create_web_client(
    aud: str,
    secret: str,
    root_url: str,
    attributes: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload = general_mappers(aud)
    payload.update(
        standardFlowEnabled=True,
        secret=secret,
        rootUrl=root_url,
        redirectUris=[f"{root_url}/*"],
        **({"attributes": attributes} if attributes else {}),
    )
    return payload


@create_client
def create_beamline_service_account_client(secret: str = "secret") -> dict[str, Any]:
    payload = beamline_service_account_mappers()
    payload.update(
        secret=secret,
        standardFlowEnabled=False,
        serviceAccountsEnabled=True,
        redirectUris=["/*"],
    )
    return payload


@create_client
def create_user_service_account_client(
    fedid: str, aud: str = "ixx-blueapi", secret: str = "secret"
) -> dict[str, Any]:
    payload = user_service_account_mappers(aud, fedid)
    payload.update(
        secret=secret,
        standardFlowEnabled=False,
        serviceAccountsEnabled=True,
        redirectUris=["/*"],
    )
    return payload


def create_clients() -> None:
    create_cli_client(client_id="ixx-cli-blueapi", aud="ixx-blueapi")
    create_cli_client(client_id="tiled-cli", aud="tiled")
    create_web_client(
        client_id="ixx-blueapi",
        aud="ixx-blueapi",
        secret="blueapi-secret",
        root_url="http://localhost:4180",
        attributes={
            "frontchannel.logout.session.required": "true",
            "use.refresh.tokens": "true",
        },
    )
    create_web_client(
        client_id="tiled",
        aud="tiled",
        secret="tiled-secret",
        root_url="http://localhost:4181",
    )
    create_beamline_service_account_client(client_id="tiled-writer")

    # A system-test service account for the admin user plus each of USERS.
    for fedid in ("admin", *USERS):
        create_user_service_account_client(
            client_id=f"system-test-blueapi-{fedid}", fedid=fedid
        )


if __name__ == "__main__":
    cleanup_components()
    create_users()
    create_clients()
