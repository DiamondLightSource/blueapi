import pytest
from bluesky_stomp.models import BasicAuthentication

from blueapi.client.client import BlueapiClient
from blueapi.config import ApplicationConfig, RestConfig, StompConfig
from blueapi.worker.event import WorkerState
from blueapi.worker.task import Task


@pytest.fixture
def training_rig_config() -> ApplicationConfig:
    return ApplicationConfig(
        stomp=StompConfig(
            host="localhost",
            auth=BasicAuthentication(username="guest", password="guest"),  # type: ignore
        ),
        api=RestConfig(host="p46-blueapi.diamond.ac.uk", port=443, protocol="https"),
    )


@pytest.fixture
def client(training_rig_config) -> BlueapiClient:
    return BlueapiClient.from_config(config=training_rig_config)


def test_get_plans(client: BlueapiClient):
    assert client.get_plans()


SPEC_SCAN = Task(
    name="spec_scan",
    params={
        "detectors": ["det"],
        "spec": {
            "axis": "sample_stage.x",
            "start": 1.0,
            "stop": 10.0,
            "num": 10,
            "type": "Line",
        },
    },
)
STEP_SCAN = Task(
    name="plan_step_scan",
    params={
        "detectors": ["det"],
        "motor": "sample_stage",
    },
)


def test_spec_scan_task(client: BlueapiClient, plan: str = "spec_scan"):
    assert client.get_plan(plan), f"In {plan} is available"

    assert client.create_and_start_task(SPEC_SCAN)

    assert (
        client.get_state() == WorkerState.IDLE
    )  # This will not be idle if the plan was working

    ## Add checks for file creation


def test_step_scan_task(client: BlueapiClient, plan: str = "plan_step_scan"):
    assert client.get_plan(plan), f"In {plan} is available"

    assert client.create_and_start_task(STEP_SCAN)

    assert (
        client.get_state() == WorkerState.IDLE
    )  # This will not be idle if the plan was working

    ## Add checks for file creation
