import inspect
import os
import time
from pathlib import Path

import pytest
from bluesky_stomp.models import BasicAuthentication
from pydantic import TypeAdapter

from blueapi.client.client import BlueapiClient
from blueapi.config import ApplicationConfig, RestConfig, StompConfig
from blueapi.service.model import DeviceResponse, PlanResponse
from blueapi.worker.task import Task

_BEAMLINE = os.environ.get("BEAMLINE", "")

# Step 1: Ensure a message bus that supports stomp is running and available:
#   src/script/start_rabbitmq.sh
#
# Step 2: Start the BlueAPI server with valid configuration:
#   blueapi -c tests/unit_tests/example_yaml/valid_stomp_config.yaml serve
#
# Step 3: Run the system tests using tox:
#   tox -e system-test

_DATA_PATH = Path(__file__).parent / "expected_data"


@pytest.fixture
def expected_plans() -> PlanResponse:
    file_name = "plans.json" if not _BEAMLINE else f"plans_{_BEAMLINE}.json"
    return TypeAdapter(PlanResponse).validate_json((_DATA_PATH / file_name).read_text())


@pytest.fixture
def expected_devices() -> DeviceResponse:
    file_name = "devices.json" if not _BEAMLINE else f"devices_{_BEAMLINE}.json"
    return TypeAdapter(DeviceResponse).validate_json(
        (_DATA_PATH / file_name).read_text()
    )


@pytest.fixture
def blueapi_client_get_methods() -> list[str]:
    # Get a list of methods that take only one argument (self)
    # This will currently return
    # ['get_plans', 'get_devices', 'get_state', 'get_all_tasks',
    # 'get_active_task','get_environment','resume', 'stop','get_oidc_config']
    return [
        method
        for method in BlueapiClient.__dict__
        if callable(getattr(BlueapiClient, method))
        and not method.startswith("__")
        and len(inspect.signature(getattr(BlueapiClient, method)).parameters) == 1
        and "self" in inspect.signature(getattr(BlueapiClient, method)).parameters
    ]


@pytest.fixture
def task_definition() -> dict[str, Task]:
    return {
        "simple_plan": Task(name="sleep", params={"time": 0.0}),
        "long_plan": Task(name="sleep", params={"time": 1.0}),
        "plan_step_scan": Task(
            name="plan_step_scan",
            params={"detectors": "det", "motor": "sample_stage.x"},
        ),
    }


@pytest.fixture(scope="package")
def config() -> ApplicationConfig:
    if _BEAMLINE == "p46":
        return ApplicationConfig(
            api=RestConfig(
                host="p46-blueapi.diamond.ac.uk", port=443, protocol="https"
            ),
        )
    else:
        return ApplicationConfig()


@pytest.fixture(scope="package", autouse=True)
def wait_for_server(config: ApplicationConfig):
    client = BlueapiClient.from_config(config=config)
    for _ in range(20):
        try:
            client.get_environment()
            return
        except ConnectionError:
            ...
        time.sleep(0.5)
    raise TimeoutError("No connection to the blueapi server")


@pytest.fixture
def config_without_auth(tmp_path: Path) -> ApplicationConfig:
    if _BEAMLINE == "p46":
        return ApplicationConfig(
            api=RestConfig(
                host="p46-blueapi.diamond.ac.uk", port=443, protocol="https"
            ),
            auth_token_path=tmp_path,
        )
    else:
        return ApplicationConfig(auth_token_path=tmp_path)


@pytest.fixture
def config_with_stomp() -> ApplicationConfig:
    if _BEAMLINE == "p46":
        return ApplicationConfig(
            stomp=StompConfig(
                host="localhost",
                auth=BasicAuthentication(username="guest", password="guest"),  # type: ignore
            ),
            api=RestConfig(
                host="p46-blueapi.diamond.ac.uk", port=443, protocol="https"
            ),
        )
    else:
        return ApplicationConfig(
            stomp=StompConfig(
                host="localhost",
                auth=BasicAuthentication(username="guest", password="guest"),  # type: ignore
            )
        )


# This client will have auth enabled if it finds cached valid token
@pytest.fixture
def client(config: ApplicationConfig) -> BlueapiClient:
    return BlueapiClient.from_config(config=config)


@pytest.fixture
def client_without_auth(config_without_auth: ApplicationConfig) -> BlueapiClient:
    return BlueapiClient.from_config(config=config_without_auth)


@pytest.fixture
def client_with_stomp(config_with_stomp: ApplicationConfig) -> BlueapiClient:
    return BlueapiClient.from_config(config=config_with_stomp)
