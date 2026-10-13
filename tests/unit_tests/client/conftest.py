from unittest.mock import Mock

import pytest
from tests.unit_tests.client.constants import (
    ACTIVE_TASK,
    DEVICES,
    ENV,
    ENVIRONMENT_ID,
    PLANS,
    TASK,
    TASKS,
)

from blueapi.client import BlueapiClient
from blueapi.client.rest import BlueapiRestClient, NotFoundError
from blueapi.service.model import EnvironmentResponse
from blueapi.worker import WorkerState


@pytest.fixture
def mock_rest() -> BlueapiRestClient:
    mock = Mock(spec=BlueapiRestClient)

    mock.get_plans.return_value = PLANS
    mock.get_plan.side_effect = lambda n: {p.name: p for p in PLANS.plans}[n]
    mock.get_devices.return_value = DEVICES
    device_map = {d.name: d for d in DEVICES.devices}

    def get_device(n: str):
        if n not in device_map:
            raise NotFoundError(404, "<Response [404]>")
        return device_map[n]

    mock.get_device.side_effect = get_device
    mock.get_state.return_value = WorkerState.IDLE
    mock.get_task.return_value = TASK
    mock.get_all_tasks.return_value = TASKS
    mock.get_active_task.return_value = ACTIVE_TASK
    mock.get_environment.return_value = ENV
    mock.delete_environment.return_value = EnvironmentResponse(
        environment_id=ENVIRONMENT_ID, initialized=False
    )
    return mock


@pytest.fixture
def client(mock_rest: Mock) -> BlueapiClient:
    return BlueapiClient(rest=mock_rest)
