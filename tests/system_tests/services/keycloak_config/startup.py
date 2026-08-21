# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mantelo==2.2.1",
#   "pydantic>=2.0",
# ]
# ///
"""Configure the local Keycloak instance used by the system tests.

Replaces the previous kcadm.sh/kcreg.sh shell script with calls to the
Keycloak Admin REST API via https://github.com/derlin/mantelo. Client
protocol mapper payloads (previously separate JSON template files) are
built here directly as pydantic models.

Assumes Keycloak is already up and healthy (the container running this
script is only started once the `keycloak` compose service reports
healthy), so there is no need to wait/retry for availability here.
"""

import os
from typing import Any

from mantelo import KeycloakAdmin
from pydantic import BaseModel, Field

SERVER = os.environ.get("KEYCLOAK_SERVER", "http://localhost:8081")
REALM = os.environ.get("KEYCLOAK_REALM", "master")
ADMIN_USERNAME = os.environ.get("KEYCLOAK_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "admin")

USERS = {"alice": "alice", "bob": "bob"}

admin = KeycloakAdmin.from_username_password(
    server_url=SERVER,
    realm_name=REALM,
    client_id="admin-cli",
    username=ADMIN_USERNAME,
    password=ADMIN_PASSWORD,
)


class ProtocolMapper(BaseModel):
    name: str
    protocol: str = "openid-connect"
    protocol_mapper: str = Field(alias="protocolMapper")
    consent_required: bool = Field(default=False, alias="consentRequired")
    config: dict[str, str]


class ClientProtocolMappers(BaseModel):
    protocol_mappers: list[ProtocolMapper] = Field(alias="protocolMappers")

    def payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


def audience_mapper(
    audience: str,
    name: str = "audience-mapper",
    extra_config: dict[str, str] | None = None,
) -> ProtocolMapper:
    return ProtocolMapper(
        name=name,
        protocolMapper="oidc-audience-mapper",
        config={
            "introspection.token.claim": "true",
            "access.token.claim": "true",
            "included.custom.audience": audience,
            **(extra_config or {}),
        },
    )


def hardcoded_claim_mapper(
    name: str, claim_value: str, extra_config: dict[str, str] | None = None
) -> ProtocolMapper:
    return ProtocolMapper(
        name=name,
        protocolMapper="oidc-hardcoded-claim-mapper",
        config={
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
    return ClientProtocolMappers(
        protocolMappers=[
            ProtocolMapper(
                name="username",
                protocolMapper="oidc-usermodel-attribute-mapper",
                config={
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
    ).payload()


def beamline_service_account_mappers() -> dict[str, Any]:
    return ClientProtocolMappers(
        protocolMappers=[
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
    ).payload()


def user_service_account_mappers(audience: str, fedid: str) -> dict[str, Any]:
    return ClientProtocolMappers(
        protocolMappers=[
            hardcoded_claim_mapper("fedid", fedid),
            audience_mapper(audience),
        ]
    ).payload()


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
    client_id: str,
    aud: str = "",
    account_type: str = "",
    fedid: str = "",
    **attrs: Any,
) -> None:
    if admin.clients.get(clientId=client_id):
        print(f">> Skipping {client_id} (exists)")
        return

    print(f">> Creating {client_id}...")

    if account_type == "BEAMLINE_SERVICE_ACCOUNT":
        payload = beamline_service_account_mappers()
    elif account_type == "USER_SERVICE_ACCOUNT":
        payload = user_service_account_mappers(aud, fedid)
    else:
        payload = general_mappers(aud)

    payload["clientId"] = client_id
    payload.update(attrs)
    admin.clients.post(payload)


# Shared by every public (no client-secret) CLI client.
CLI_ATTRIBUTES = {
    "frontchannel.logout.session.required": "true",
    "oauth2.device.authorization.grant.enabled": "true",
    "use.refresh.tokens": "true",
    "backchannel.logout.session.required": "true",
}

CLIENT_DEFINITIONS: list[dict[str, Any]] = [
    {
        "client_id": "ixx-cli-blueapi",
        "aud": "ixx-blueapi",
        "standardFlowEnabled": False,
        "publicClient": True,
        "redirectUris": ["/*"],
        "attributes": CLI_ATTRIBUTES,
    },
    {
        "client_id": "ixx-blueapi",
        "aud": "ixx-blueapi",
        "standardFlowEnabled": True,
        "secret": "blueapi-secret",
        "rootUrl": "http://localhost:4180",
        "redirectUris": ["http://localhost:4180/*"],
        "attributes": {
            "frontchannel.logout.session.required": "true",
            "use.refresh.tokens": "true",
        },
    },
    {
        "client_id": "tiled",
        "aud": "tiled",
        "standardFlowEnabled": True,
        "secret": "tiled-secret",
        "rootUrl": "http://localhost:4181",
        "redirectUris": ["http://localhost:4181/*"],
    },
    {
        "client_id": "tiled-cli",
        "aud": "tiled",
        "standardFlowEnabled": False,
        "publicClient": True,
        "redirectUris": ["/*"],
        "attributes": CLI_ATTRIBUTES,
    },
    {
        "client_id": "tiled-writer",
        "account_type": "BEAMLINE_SERVICE_ACCOUNT",
        "secret": "secret",
        "standardFlowEnabled": False,
        "serviceAccountsEnabled": True,
        "redirectUris": ["/*"],
    },
    # A system-test service account for the admin user plus each of USERS.
    *(
        {
            "client_id": f"system-test-blueapi-{fedid}",
            "aud": "ixx-blueapi",
            "account_type": "USER_SERVICE_ACCOUNT",
            "fedid": fedid,
            "secret": "secret",
            "standardFlowEnabled": False,
            "serviceAccountsEnabled": True,
            "redirectUris": ["/*"],
        }
        for fedid in ("admin", *USERS)
    ),
]


def create_clients() -> None:
    for definition in CLIENT_DEFINITIONS:
        create_client(**definition)


if __name__ == "__main__":
    cleanup_components()
    create_users()
    create_clients()
