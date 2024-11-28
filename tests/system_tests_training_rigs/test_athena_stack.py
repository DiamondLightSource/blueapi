import pytest
from bluesky_stomp.models import BasicAuthentication

from blueapi.client.client import BlueapiClient
from blueapi.config import ApplicationConfig, RestConfig, StompConfig


@pytest.fixture
def training_rig_config() -> ApplicationConfig:
    return ApplicationConfig(
        stomp=StompConfig(
            host="localhost",
            port=123,
            auth=BasicAuthentication(username="guest", password="guest"),  # type: ignore
        ),
        api=RestConfig(
            host="https://p46-blueapi.diamond.ac.uk/", port=80, protocol="https"
        ),
    )


@pytest.fixture
def client(training_rig_config) -> BlueapiClient:
    return BlueapiClient.from_config(config=training_rig_config)


def test_get_plans(client: BlueapiClient):
    assert client.get_plans()
