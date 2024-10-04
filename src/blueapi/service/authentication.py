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


class Authentication:
    """
    Authentication class handles the authentication process using either
    device code flow or PKCE flow.

    Attributes:
        client_id (str): The client ID for the authentication.
        authentication_url (str): The URL for authentication.
        audience (list[str]): The audience for the authentication.
        token_url (str): The URL to obtain the token.
        openid_config (str): The OpenID configuration URL.
        issuer (str): The issuer of the token.
        user_name (str | None): The username obtained from the token.
        fedid (str | None): The federated ID obtained from the token.
        jwks_client (jwt.PyJWKClient): The JWKS client for verifying tokens.
        token_file_path (str): The file path to save the token.
        token (None | dict[str, Any]): The token dictionary.

    Methods:
        __init__(authentication_type: AuthenticationType = AuthenticationType.DEVICE,
                token_file_path: str = "token") -> None:
            Initializes the Authentication class with the specified authentication type
            and token file path.

        get_device_code() -> str:
            Obtains the device code for device code flow.

        poll_for_token(device_code: str, timeout: float = 30,
        polling_interval: float = 0.5)
        -> dict[str, Any]:
            Polls for the token using the device code.

        verify_token(token: str, verify_expiration: bool = True)
        -> tuple[bool, Exception | None]:
            Verifies the provided token.

        refresh_auth_token() -> bool:
            Refreshes the authentication token.

        save_token(token: dict[str, Any]) -> None:
            Saves the token to a file.

        load_token() -> None:
            Loads the token from a file.

        start_device_flow() -> None:
            Starts the device flow for authentication.
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

        self.user_name: str | None = None
        self.fedid: str | None = None
        # Get the OpenID Connect configuration and configure the JWKS client
        oidc_config = requests.get(self.openid_config).json()
        self.jwks_client = jwt.PyJWKClient(oidc_config["jwks_uri"])

        # Token file path
        self.token_file_path = token_file_path
        self.token: None | dict[str, Any] = None
        self.load_token()

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
            # Send POST request
            response = requests.post(
                self.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": self.client_id,
                },
            )

            # Check response status code
            if response.status_code == HTTPStatus.OK:
                return response.json()
            if response.status_code == HTTPStatus.BAD_REQUEST:
                polling_interval += 0.5
            time.sleep(polling_interval)

        raise TimeoutError("Polling timed out")

    def verify_token(
        self, token: str, verify_expiration: bool = True
    ) -> tuple[bool, Exception | None]:
        signing_key = self.jwks_client.get_signing_key_from_jwt(token)
        try:
            decode = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_exp": verify_expiration},
                verify=True,
                audience=self.audience,
                issuer=self.issuer,
                leeway=5,
            )
            if decode:
                self.user_name = decode.get("name")
                self.fedid = decode.get("fedid")
                return (True, None)
        except jwt.PyJWTError as e:
            return (False, e)

        return (False, Exception("Invalid token"))

    def refresh_auth_token(self) -> bool:
        if self.token:
            # Send POST request
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
        # Convert the token dictionary to a JSON string
        token_json = json.dumps(token)

        # Convert the JSON string to bytes
        token_bytes = token_json.encode("utf-8")

        # Encode the bytes using base64
        token_base64 = base64.b64encode(token_bytes)

        # Save the base64 encoded bytes to a file

        with open(self.token_file_path, "wb") as token_file:
            token_file.write(token_base64)

    def load_token(self) -> None:
        if not os.path.exists(self.token_file_path):
            return None
        with open(self.token_file_path, "rb") as token_file:
            token_base64 = token_file.read()

            # Decode the base64 encoded bytes
            token_bytes = base64.b64decode(token_base64)

            # Convert the bytes back to a JSON string
            token_json = token_bytes.decode("utf-8")

            # Convert the JSON string back to a dictionary
            self.token = json.loads(token_json)

    def start_device_flow(self) -> None:
        # Check if we have a valid token
        if self.token:
            valid_token, exception = self.verify_token(self.token["access_token"])
            if valid_token:
                print("Token verified")
                return
            elif isinstance(exception, jwt.ExpiredSignatureError):
                if self.refresh_auth_token():
                    return
        # Send Request to get fresh token as token is not valid
        # and refresh token is not available
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
                # Verify Token
                verify, exception = self.verify_token(auth_token_json["access_token"])
                if verify:
                    print("Token verified")
                    self.save_token(auth_token_json)
                else:
                    print("Unauthorized access")
                    return
        else:
            print("Unauthorized access")
            return
        print(f"Logged in as {self.user_name} with fed-id {self.fedid}")
