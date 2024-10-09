import base64
import json
import os
import time
from enum import Enum
from http import HTTPStatus
from typing import Any

import jwt
import requests
from dotenv import load_dotenv


class AuthenticationType(Enum):
    DEVICE = "device"
    PKCE = "pkce"


class TokenManager:
    """
    TokenManager class handles the token verification and refreshing.

    Attributes:
        client_id (str): The client ID for the authentication.
        token_url (str): The URL to obtain the token.
        audience (list[str]): The audience for the authentication.
        issuer (str): The issuer of the token.
        jwks_client (jwt.PyJWKClient): The JWKS client for verifying tokens.
        token_file_path (str): The file path to save the token.
        token (None | dict[str, Any]): The token dictionary.
    """

    # Will move this to a computed field in ApplicationConfig
    # Get the OpenID Connect configuration and configure the JWKS client
    oidc_config = requests.get(
        "https://authn.diamond.ac.uk/realms/master/.well-known/openid-configuration"
    ).json()
    jwks_uri = oidc_config["jwks_uri"]
    issuer = oidc_config["issuer"]
    token_url = oidc_config["token_endpoint"]
    jwks_client = jwt.PyJWKClient(jwks_uri)
    audience = "blueapi"

    def __init__(
        self,
        client_id: str,
        token_file_path: str = "token",
    ) -> None:
        self.client_id = client_id
        self.token_file_path = token_file_path
        self.token: None | dict[str, Any] = None
        self.load_token()

    @classmethod
    def verify_token(
        cls, token: str, verify_expiration: bool = True
    ) -> tuple[bool, Exception | None]:
        try:
            decode = cls.decode_jwt(token, verify_expiration)
            if decode:
                return (True, None)
        except jwt.PyJWTError as e:
            print(e)
            return (False, e)

        return (False, Exception("Invalid token"))

    @classmethod
    def decode_jwt(cls, token: str, verify_expiration: bool = True):
        signing_key = cls.jwks_client.get_signing_key_from_jwt(token)
        decode = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_exp": verify_expiration},
            verify=True,
            audience=cls.audience,
            issuer=cls.issuer,
            leeway=5,
        )
        return decode

    @classmethod
    def userInfo(cls, token: str) -> tuple[str | None, str | None]:
        try:
            decode = cls.decode_jwt(token)
            if decode:
                return (decode["name"], decode["fedid"])
            else:
                return (None, None)
        except jwt.PyJWTError as _:
            return (None, None)

    def refresh_auth_token(self) -> bool:
        if self.token:
            response = requests.post(
                self.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "client_id": self.client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": self.token["refresh_token"],
                },
            )
            if response.status_code == HTTPStatus.OK:
                self.save_token(response.json())
                return True
            else:
                return False
        else:
            return False

    def save_token(self, token: dict[str, Any]) -> None:
        token_json = json.dumps(token)
        token_bytes = token_json.encode("utf-8")
        token_base64 = base64.b64encode(token_bytes)
        with open(self.token_file_path, "wb") as token_file:
            token_file.write(token_base64)

    def load_token(self) -> None:
        if not os.path.exists(self.token_file_path):
            return None
        with open(self.token_file_path, "rb") as token_file:
            token_base64 = token_file.read()
            token_bytes = base64.b64decode(token_base64)
            token_json = token_bytes.decode("utf-8")
            self.token = json.loads(token_json)


class Authenticator:
    """
    Authenticator class handles the authentication process using either
    device code flow or PKCE flow.

    Attributes:
        client_id (str): The client ID for the authentication.
        authentication_url (str): The URL for authentication.
        audience (list[str]): The audience for the authentication.
        token_manager (TokenManager): The TokenManager instance.
    """

    def __init__(
        self,
        authentication_type: AuthenticationType = AuthenticationType.DEVICE,
        token_file_path: str = "token",
    ) -> None:
        load_dotenv()
        if authentication_type == AuthenticationType.DEVICE:
            self.client_id: str = os.getenv("DEVICE_CLIENT_ID", "")
            self.authentication_url: str = os.getenv("DEVICE_AUTHENTICATION_URL", "")
            self.audience: list[str] = os.getenv("DEVICE_AUDIENCES", "").split(" ")
        else:
            self.client_secret: str = os.getenv("PKCE_CLIENT_SECRET", "")
            if self.client_secret == "":
                raise Exception("Missing environment variables")
            self.client_id = os.getenv("PKCE_CLIENT_ID", "")
            self.authentication_url = os.getenv("PKCE_AUTHENTICATION_URL", "")
            self.audience = os.getenv("PKCE_AUDIENCES", "").split(" ")

        self.token_url: str = os.getenv("TOKEN_URL", "")
        self.openid_config: str = os.getenv("OPEN_ID_CONFIG", "")
        self.issuer = os.getenv("ISSUER")
        if any(
            [
                self.client_id == "",
                self.authentication_url == "",
                self.audience == "",
                self.token_url == "",
                self.openid_config == "",
                self.issuer == "",
            ]
        ):
            raise Exception("Missing environment variables")

        self.token_manager = TokenManager(
            client_id=self.client_id,
            token_file_path=token_file_path,
        )

    def get_device_code(self):
        response = requests.post(
            self.token_url,
            data={
                "client_id": self.client_id,
                "scope": "openid profile offline_access",
                "audience": self.audience,
            },
        )
        response_data = response.json()
        if response.status_code == 200:
            return response_data["device_code"]
        else:
            raise Exception("Failed to get device code.")

    def poll_for_token(
        self, device_code: str, timeout: float = 30, polling_interval: float = 0.5
    ) -> dict[str, Any]:
        too_late = time.time() + timeout
        while time.time() < too_late:
            response = requests.post(
                self.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": self.client_id,
                },
            )
            if response.status_code == HTTPStatus.OK:
                return response.json()
            if response.status_code == HTTPStatus.BAD_REQUEST:
                polling_interval += 0.5
            time.sleep(polling_interval)

        raise TimeoutError("Polling timed out")

    def start_device_flow(self) -> None:
        if self.token_manager.token:
            valid_token, exception = self.token_manager.verify_token(
                self.token_manager.token["access_token"]
            )
            if valid_token:
                print("Token verified")
                return
            elif isinstance(exception, jwt.ExpiredSignatureError):
                if self.token_manager.refresh_auth_token():
                    return

        response = requests.post(
            self.authentication_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"client_id": self.client_id},
        )

        if response.status_code == HTTPStatus.OK:
            response_json = response.json()
            device_code: str = response_json.get("device_code")
            print(
                "Please login from this URL:- "
                f"{response_json['verification_uri_complete']}"
            )
            auth_token_json = self.poll_for_token(device_code)
            if auth_token_json:
                print(auth_token_json)
                verify, exception = TokenManager.verify_token(
                    auth_token_json["access_token"]
                )
                if verify:
                    print("Token verified")
                    self.token_manager.save_token(auth_token_json)
                else:
                    print("Unauthorized access")
                    return
        else:
            print("Unauthorized access")
            return
        userName, fedid = TokenManager.userInfo(auth_token_json["access_token"])
        print(f"Logged in as {userName} with fed-id {fedid}")
