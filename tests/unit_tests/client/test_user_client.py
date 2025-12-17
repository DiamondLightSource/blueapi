import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from dodal.plans.wrapped import count

from blueapi.client.client import BlueapiClient
from blueapi.client.event_bus import EventBusClient
from blueapi.client.rest import BlueapiRestClient
from blueapi.client.user_client import UserClient
from blueapi.service.model import DeviceResponse, PlanResponse

UNIT_TEST_DIRECTORY = Path(__file__).parent.parent


BLUEAPI_CONFIG_PATH = os.path.join(
    UNIT_TEST_DIRECTORY, "valid_example_config/client.yaml"
)


class MockDevice:
    def __init__(self, device: str):
        self.device = device
        self.name = device


class MockResponse:
    def __init__(self, devices: list):
        self.devices = devices


@pytest.fixture(autouse=True)
def client():
    client = UserClient(BLUEAPI_CONFIG_PATH, "cm12345-1", callback=True)

    client._rest = Mock(BlueapiRestClient)
    client._events = Mock(EventBusClient)

    client._events.__enter__ = Mock(return_value=client._events)
    client._events.__exit__ = Mock(return_value=None)

    return client


@pytest.fixture(autouse=True)
def client_without_callback():
    client_without_callback = UserClient(
        BLUEAPI_CONFIG_PATH, "cm12345-1", callback=False
    )

    return client_without_callback


def test_blueapi_python_client(client: UserClient):
    assert isinstance(client, BlueapiClient)
    assert isinstance(client, UserClient)


def test_blueapi_python_client_change_session(client: UserClient):
    new_session = "cm54321-1"
    client.change_session(new_session)
    assert client.instrument_session == new_session


def test_blueapi_python_client_run(client: UserClient):
    # Patch instance methods so run executes but no re calls happen.
    with (
        patch.object(client, "run_task", return_value=Mock()),
        patch.object(
            client, "create_and_start_task", return_value=Mock(task_id="t-fake")
        ),
        patch.object(client, "create_task", return_value=Mock(task_id="t-fake")),
        patch.object(client, "start_task", return_value=Mock(task_id="t-fake")),
    ):
        assert client._events is not None
        # Ensure the mocked event client can be used as a context manager if run uses it
        client._events.__enter__ = Mock(return_value=client._events)
        client._events.__exit__ = Mock(return_value=None)

        # Call run while the instance methods are patched
        client.run(count)
        client.run("count")


def test_blueapi_python_client_without_callback_run(
    client_without_callback: UserClient,
):
    # Patch instance methods so run executes but no calls happen
    with (
        patch.object(client_without_callback, "run_task", return_value=Mock()),
        patch.object(
            client_without_callback,
            "create_and_start_task",
            return_value=Mock(task_id="t-fake"),
        ),
        patch.object(
            client_without_callback, "create_task", return_value=Mock(task_id="t-fake")
        ),
        patch.object(
            client_without_callback, "start_task", return_value=Mock(task_id="t-fake")
        ),
    ):
        # Ensure the mocked event client can be used as a context manager if run uses it
        client_without_callback._events = Mock(EventBusClient)
        client_without_callback._events.__enter__ = Mock(
            return_value=client_without_callback._events
        )
        client_without_callback._events.__exit__ = Mock(return_value=None)

        client_without_callback.run(count)


@pytest.mark.parametrize(
    "plan, args, kwargs",
    (
        ["plan", (), {}],
        [count, ["det1", "det2"], {}],
        [count, ["det1", "det2"], {"num": 2}],
        [count, (), {"detectors": ["det1", "det2"]}],
    ),
)
def test_run_with_valid_paraneters(client: UserClient, plan, args: tuple, kwargs: dict):
    # Patch instance methods so run executes but no re calls happen.
    with (
        patch.object(client, "run_task", return_value=Mock()),
        patch.object(
            client, "create_and_start_task", return_value=Mock(task_id="t-fake")
        ),
        patch.object(client, "create_task", return_value=Mock(task_id="t-fake")),
        patch.object(client, "start_task", return_value=Mock(task_id="t-fake")),
    ):
        assert client._events is not None
        # Ensure the mocked event client can be used as a context manager if run uses it
        client._events.__enter__ = Mock(return_value=client._events)
        client._events.__exit__ = Mock(return_value=None)

        client.run(plan, *args, **kwargs)


@pytest.mark.parametrize(
    "plan, args, kwargs",
    (
        [None, (), {}],
        ["plan", ["det1", "det2"], {}],
        ["plan", ["det1", "det2"], {"num": 2}],
    ),
)
def test_run_fails_with_invalid_parameters(
    client: UserClient, plan, args: tuple, kwargs: dict
):
    # Patch instance methods so run executes but no re calls happen.
    with (
        patch.object(client, "run_task", return_value=Mock()),
        patch.object(
            client, "create_and_start_task", return_value=Mock(task_id="t-fake")
        ),
        patch.object(client, "create_task", return_value=Mock(task_id="t-fake")),
        patch.object(client, "start_task", return_value=Mock(task_id="t-fake")),
    ):
        assert client._events is not None
        # Ensure the mocked event client can be used as a context manager if run uses it
        client._events.__enter__ = Mock(return_value=client._events)
        client._events.__exit__ = Mock(return_value=None)

        # Call run while the instance methods are patched
        with pytest.raises(ValueError):  # noqa
            client.run(plan, *args, **kwargs)


def test_return_detectors(client: UserClient):
    # Mock the expected detector list response

    # Create a method mock for get_detectors
    client.get_devices = Mock(
        DeviceResponse,
        return_value=MockResponse([MockDevice("det1"), MockDevice("det2")]),
    )

    # Call the method under test
    result = client.return_detectors()

    # Verify the result matches our expected data

    # Verify the REST client was called correctly
    client.get_devices.assert_called_once()

    assert isinstance(result, list)


def test_show_devices(client: UserClient):
    # Create a method mock for get_detectors
    client.get_devices = Mock(
        DeviceResponse,
        return_value=MockResponse([MockDevice("det1"), MockDevice("det2")]),
    )

    client.show_devices()
    client.get_devices.assert_called_once()


class MockPlan:
    def __init__(self, device: str):
        self.name = device


class MockPlanResponse:
    def __init__(self, plans: list):
        self.plans = plans


def test_show_plans(client: UserClient):
    # Create a method mock for get_detectors
    client.get_plans = Mock(
        PlanResponse,
        return_value=MockPlanResponse([MockPlan("count"), MockPlan("test")]),
    )

    client.show_plans()
    client.get_plans.assert_called_once()
