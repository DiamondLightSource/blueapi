import asyncio
import datetime
import logging
import webbrowser
from dataclasses import dataclass
from typing import Any, Dict

import requests

AUTH_SERVER = "https://authalpha.diamond.ac.uk/cas/oauth2.0/accessToken?response_type=device_code&client_id=oidc_diamond_ac_uk&scope=openid"


class ServerException(Exception):
    ...


@dataclass
class AccessToken:
    access_token: str
    expires_in: int
    time_of_retrieval: float = datetime.datetime.now().timestamp()


LOGGER = logging.getLogger(__name__)


async def poll_for_token(
    seconds_remaining: float, device_code: str, poll_interval: float = 1
) -> AccessToken:
    request = requests.request(
        "POST",
        AUTH_SERVER + f"&device_code={device_code}",
    )
    if request.status_code != 200:
        if seconds_remaining > 0:
            await asyncio.sleep(poll_interval)
            return await poll_for_token(
                seconds_remaining - poll_interval,
                device_code,
                poll_interval=poll_interval,
            )
        else:
            raise TimeoutError("Please try logging in again")

    data: Dict[str, Any] = request.json()
    print(data)
    return AccessToken(data["access_token"], data["expires_in"])


async def login() -> AccessToken:
    req = requests.request("POST", AUTH_SERVER)
    if req.status_code != 200:
        raise ServerException(req.status_code)

    req_json = req.json()
    verification_uri = req_json["verification_uri"]
    user_code = req_json["user_code"]
    device_code = req_json["device_code"]
    expires_in = req_json["expires_in"]

    LOGGER.info(
        f"Please log into {verification_uri} using code {user_code}. "
        + f"Expires in {expires_in} seconds"
    )
    print(
        f"Please log into {verification_uri} using code {user_code}. "
        + f"Expires in {expires_in} seconds"
    )
    webbrowser.open(verification_uri)

    return await poll_for_token(expires_in, device_code)
