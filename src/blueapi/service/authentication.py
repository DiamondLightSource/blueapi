import json
import os
import time
from enum import Enum
from http import HTTPStatus

import jwt
import requests
from cryptography.fernet import Fernet
from dotenv import load_dotenv


class AuthenticationType(Enum):
    DEVICE = "device"
    PKCE = "pkce"


class Authentication:
    def __init__(self, authentication_type: AuthenticationType):
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

    def get_device_code(self):
        response = requests.post(
            self.token_url,
            data={
                "client_id": self.client_id,
                "scope": "openid profile offline_access",
            },
        )
        response_data = response.json()
        if response.status_code == 200:
            return response_data["device_code"]
        else:
            raise Exception(f"Failed to get device code: {response_data}")

    def poll_for_token(
        self, device_code: str, timeout: float = 30, polling_interval: float = 0.5
    ) -> dict | None:
        too_late = time.time() + timeout
        while time.time() < too_late:
            # Send POST request
            response = requests.post(
                self.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "device_code": device_code,
                    "client_id": self.client_id,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )

            # Check response status code
            if response.status_code == HTTPStatus.OK:
                return response.json()
            if response.status_code == HTTPStatus.BAD_REQUEST:
                polling_interval += 0.5
            time.sleep(polling_interval)

        raise TimeoutError("Polling timed out")

    def validate_token(self, token):
        # Verify Token
        sigining_key = self.jwks_client.get_signing_key_from_jwt(token["access_token"])
        try:
            decode = jwt.decode(
                token["access_token"],
                sigining_key.key,
                algorithms=["RS256"],
                # options={
                #     "verify_exp": False
                # },  # This need to be removed and we need to refresh our token
                verify=True,
                audience=self.audience,
                issuer=self.issuer,
                leeway=5,
            )
        except jwt.ExpiredSignatureError:
            print("Token Expired")
        if decode:
            self.user_name = decode["name"]
            self.fedid = decode["fedid"]
            return True
        return False

    def save_token(self, token):
        # Encrypt and then save auth_token_response to a file
        # Generate and save a key (do this once and keep the key secure)
        key = Fernet.generate_key()
        with open("secret.key", "wb") as key_file:
            key_file.write(key)

        # Load the key
        with open("secret.key", "rb") as key_file:
            key = key_file.read()

        cipher_suite = Fernet(key)

        # Encrypt a message
        token = cipher_suite.encrypt(json.dumps(token).encode())
        with open("token.txt", "wb") as token_file:
            token_file.write(token)

    def load_token(self):
        # Load the key
        with open("secret.key", "rb") as key_file:
            key = key_file.read()

        cipher_suite = Fernet(key)
        # Decrypt the message
        with open("token.txt", "rb") as token_file:
            token = token_file.read()
            token = cipher_suite.decrypt(token).decode()
            # This print is just for testing purposes
            print(token)

    def start_device_flow(self):
        response = requests.post(
            self.authentication_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"client_id": self.client_id},
        )

        if response.status_code == HTTPStatus.OK:
            # TODO: (Not Done because have not figured out how to refresh the token)
            # Before sending the request, we need to check if we already have a token
            # If we have a token, we need to validate the token
            # and use that token to make the request
            # If the token is not valid, we need to get a new token
            response_json = response.json()
            device_code: str = response_json.get("device_code")
            print(
                "Please login from this URL:- "
                f"{response_json['verification_uri_complete']}"
            )
            auth_token_json = self.poll_for_token(device_code)
            # Verify Token
            if self.validate_token(auth_token_json):
                print("Token verified")
            else:
                return
            print(f"Logged in as {self.user_name} with fed-id {self.fedid}")
            self.save_token(auth_token_json)
            self.load_token()
        else:
            print("Unauthorized access")
