import base64
import json
import os
import time
from enum import Enum
from http import HTTPStatus
from typing import Any

import jwt
import requests

from blueapi.config import (
    BaseAuthConfig,
    CLIAuthConfig,
    OauthConfig,
)


class AuthenticationType(Enum):
    DEVICE = "device"
    PKCE = "pkce"


class Authenticator:
    def __init__(
        self,
        oauth: OauthConfig,
        baseAuthConfig: BaseAuthConfig,
    ):
        self.oauth: OauthConfig = oauth
        self.baseAuthConfig: BaseAuthConfig = baseAuthConfig

    def verify_token(self, token: str, verify_expiration: bool = True) -> bool:
        self.decode_jwt(token, verify_expiration)
        return True

    def decode_jwt(self, token: str, verify_expiration: bool = True) -> dict[str, str]:
        signing_key = jwt.PyJWKClient(self.oauth.jwks_uri).get_signing_key_from_jwt(
            token
        )
        decode: dict[str, str] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_exp": verify_expiration},
            verify=True,
            audience=self.baseAuthConfig.client_audience,
            issuer=self.oauth.issuer,
            leeway=5,
        )
        return decode

    def print_user_info(self, token: str) -> None:
        decode: dict[str, str] = self.decode_jwt(token)
        print(f'Logged in as {decode.get("name")} with fed-id {decode.get("fedid")}')


class TokenManager:
    def __init__(self, oauth: OauthConfig, cliAuth: CLIAuthConfig) -> None:
        self.oauth: OauthConfig = oauth
        self.cliAuth: CLIAuthConfig = cliAuth
        self.token: Any = None
        self.authenticator: Authenticator = Authenticator(self.oauth, self.cliAuth)
        self.load_token()

    def logout(self) -> None:
        if os.path.exists(os.path.expanduser(self.cliAuth.token_file_path)):
            os.remove(os.path.expanduser(self.cliAuth.token_file_path))

    def refresh_auth_token(self) -> bool:
        if self.token:
            response = requests.post(
                self.oauth.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "client_id": self.cliAuth.client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": self.token["refresh_token"],
                },
            )
            if response.status_code == HTTPStatus.OK:
                self.save_token(response.json())
                self.load_token()
                return True
        return False

    def save_token(self, token: dict[str, Any]) -> None:
        token_json: str = json.dumps(token)
        token_bytes: bytes = token_json.encode("utf-8")
        token_base64: bytes = base64.b64encode(token_bytes)
        with open(os.path.expanduser(self.cliAuth.token_file_path), "wb") as token_file:
            token_file.write(token_base64)

    def load_token(self) -> None:
        if not os.path.exists(os.path.expanduser(self.cliAuth.token_file_path)):
            return
        with open(os.path.expanduser(self.cliAuth.token_file_path), "rb") as token_file:
            token_base64: bytes = token_file.read()
            token_bytes: bytes = base64.b64decode(token_base64)
            token_json: str = token_bytes.decode("utf-8")
            self.token = json.loads(token_json)

    def get_device_code(self):
        response: requests.Response = requests.post(
            self.oauth.token_url,
            data={
                "client_id": self.cliAuth.client_id,
                "scope": "openid profile offline_access",
                "audience": self.cliAuth.client_audience,
            },
        )
        response_data: dict[str, str] = response.json()
        if response.status_code == 200:
            return response_data["device_code"]
        raise Exception("Failed to get device code.")

    def poll_for_token(
        self, device_code: str, timeout: float = 30, polling_interval: float = 0.5
    ) -> dict[str, Any]:
        too_late: float = time.time() + timeout
        while time.time() < too_late:
            response = requests.post(
                self.oauth.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": self.cliAuth.client_id,
                },
            )
            if response.status_code == HTTPStatus.OK:
                return response.json()
            if response.status_code == HTTPStatus.BAD_REQUEST:
                polling_interval += 0.5
            time.sleep(polling_interval)

        raise TimeoutError("Polling timed out")

    def start_device_flow(self) -> None:
        if self.token:
            try:
                is_token_vaild: bool = self.authenticator.verify_token(
                    self.token["access_token"]
                )
                if is_token_vaild:
                    self.load_token()
                    self.authenticator.print_user_info(self.token["access_token"])
                    return
            except jwt.ExpiredSignatureError:
                if self.refresh_auth_token():
                    self.authenticator.print_user_info(self.token["access_token"])
                    return

        response: requests.Response = requests.post(
            self.oauth.device_auth_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"client_id": self.cliAuth.client_id},
        )

        if response.status_code == HTTPStatus.OK:
            response_json: Any = response.json()
            device_code: str = response_json.get("device_code")
            print(
                "Please login from this URL:- "
                f"{response_json['verification_uri_complete']}"
            )
            auth_token_json: dict[str, Any] = self.poll_for_token(device_code)
            valid_token: bool = self.authenticator.verify_token(
                auth_token_json["access_token"]
            )
            if valid_token:
                self.save_token(auth_token_json)
                self.authenticator.print_user_info(auth_token_json["access_token"])
