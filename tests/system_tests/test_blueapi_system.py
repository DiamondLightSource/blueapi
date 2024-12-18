import time

import backoff
import pytest
from pydantic import TypeAdapter

from blueapi.client.client import (
    BlueapiClient,
    BlueskyRemoteControlError,
)
from blueapi.client.event_bus import AnyEvent
from blueapi.config import (
    OIDCConfig,
)
from blueapi.service.model import (
    DeviceResponse,
    EnvironmentResponse,
    PlanResponse,
    TaskResponse,
    WorkerTask,
)
from blueapi.worker.event import TaskStatus, WorkerEvent, WorkerState
from blueapi.worker.task import Task
from blueapi.worker.task_worker import TrackableTask
from tests.system_tests.common import (
    clean_existing_tasks,
    disable_side_effects,
    requires_auth,
)


@requires_auth
def test_cannot_access_endpoints(
    client_without_auth: BlueapiClient, blueapi_client_get_methods: list[str]
):
    blueapi_client_get_methods.remove(
        "get_oidc_config"
    )  # get_oidc_config can be accessed without auth
    for get_method in blueapi_client_get_methods:
        with pytest.raises(BlueskyRemoteControlError, match=r"<Response \[401\]>"):
            getattr(client_without_auth, get_method)()


@requires_auth
def test_can_get_oidc_config_without_auth(client_without_auth: BlueapiClient):
    assert client_without_auth.get_oidc_config() == OIDCConfig(
        well_known_url="https://example.com/realms/master/.well-known/openid-configuration",
        client_id="blueapi-cli",
    )


def test_get_plans(client: BlueapiClient, expected_plans: PlanResponse):
    retrieved_plans = client.get_plans()
    retrieved_plans.plans.sort(key=lambda x: x.name)
    expected_plans.plans.sort(key=lambda x: x.name)

    assert retrieved_plans == expected_plans


def test_get_plans_by_name(client: BlueapiClient, expected_plans: PlanResponse):
    for plan in expected_plans.plans:
        assert client.get_plan(plan.name) == plan


def test_get_non_existent_plan(client: BlueapiClient):
    with pytest.raises(KeyError, match="{'detail': 'Item not found'}"):
        client.get_plan("Not exists")


def test_get_devices(client: BlueapiClient, expected_devices: DeviceResponse):
    retrieved_devices = client.get_devices()
    retrieved_devices.devices.sort(key=lambda x: x.name)
    expected_devices.devices.sort(key=lambda x: x.name)

    assert retrieved_devices == expected_devices


def test_get_device_by_name(client: BlueapiClient, expected_devices: DeviceResponse):
    for device in expected_devices.devices:
        assert client.get_device(device.name) == device


def test_get_non_existent_device(client: BlueapiClient):
    with pytest.raises(KeyError, match="{'detail': 'Item not found'}"):
        client.get_device("Not exists")


@disable_side_effects
def test_create_task_and_delete_task_by_id(
    client: BlueapiClient, task_definition: dict[str, Task]
):
    create_task = client.create_task(task_definition["simple_plan"])
    client.clear_task(create_task.task_id)


def test_create_task_validation_error(client: BlueapiClient):
    with pytest.raises(KeyError, match="{'detail': 'Item not found'}"):
        client.create_task(Task(name="Not-exists", params={"Not-exists": 0.0}))


@disable_side_effects
def test_get_all_tasks(client: BlueapiClient, task_definition: dict[str, Task]):
    clean_existing_tasks(client)
    created_tasks: list[TaskResponse] = []
    for task in [task_definition["simple_plan"], task_definition["long_plan"]]:
        created_task = client.create_task(task)
        created_tasks.append(created_task)
    task_ids = [task.task_id for task in created_tasks]

    task_list = client.get_all_tasks()
    for trackable_task in task_list.tasks:
        assert trackable_task.task_id in task_ids
        assert trackable_task.is_complete is False and trackable_task.is_pending is True

    for task_id in task_ids:
        client.clear_task(task_id)


@disable_side_effects
def test_get_task_by_id(client: BlueapiClient, task_definition: dict[str, Task]):
    created_task = client.create_task(task_definition["simple_plan"])

    get_task = client.get_task(created_task.task_id)
    assert (
        get_task.task_id == created_task.task_id
        and get_task.is_pending
        and not get_task.is_complete
        and len(get_task.errors) == 0
    )

    client.clear_task(created_task.task_id)


def test_get_non_existent_task(client: BlueapiClient):
    with pytest.raises(KeyError, match="{'detail': 'Item not found'}"):
        client.get_task("Not-exists")


def test_delete_non_existent_task(client: BlueapiClient):
    with pytest.raises(KeyError, match="{'detail': 'Item not found'}"):
        client.clear_task("Not-exists")


@disable_side_effects
def test_put_worker_task(client: BlueapiClient, task_definition: dict[str, Task]):
    created_task = client.create_task(task_definition["simple_plan"])
    client.start_task(WorkerTask(task_id=created_task.task_id))
    active_task = client.get_active_task()
    assert active_task.task_id == created_task.task_id
    client.clear_task(created_task.task_id)


@disable_side_effects
def test_put_worker_task_fails_if_not_idle(
    client: BlueapiClient, task_definition: dict[str, Task]
):
    small_task = client.create_task(task_definition["simple_plan"])
    long_task = client.create_task(task_definition["long_plan"])

    client.start_task(WorkerTask(task_id=long_task.task_id))
    active_task = client.get_active_task()
    assert active_task.task_id == long_task.task_id

    with pytest.raises(BlueskyRemoteControlError) as exception:
        client.start_task(WorkerTask(task_id=small_task.task_id))
    assert "<Response [409]>" in str(exception)
    client.abort()
    client.clear_task(small_task.task_id)
    client.clear_task(long_task.task_id)


def test_get_worker_state(client: BlueapiClient):
    assert client.get_state() == WorkerState.IDLE


@disable_side_effects
def test_set_state_transition_error(client: BlueapiClient):
    with pytest.raises(BlueskyRemoteControlError) as exception:
        client.resume()
    assert "<Response [400]>" in str(exception)
    with pytest.raises(BlueskyRemoteControlError) as exception:
        client.pause()
    assert "<Response [400]>" in str(exception)


@disable_side_effects
def test_get_task_by_status(client: BlueapiClient, task_definition: dict[str, Task]):
    clean_existing_tasks(client)
    task_1 = client.create_task(task_definition["simple_plan"])
    task_2 = client.create_task(task_definition["simple_plan"])
    task_by_pending = client.get_all_tasks()
    # https://github.com/DiamondLightSource/blueapi/issues/680
    # task_by_pending = client.get_tasks_by_status(TaskStatusEnum.PENDING)
    assert len(task_by_pending.tasks) == 2
    # Check if all the tasks are pending
    for task in task_by_pending.tasks:
        trackable_task = TypeAdapter(TrackableTask).validate_python(task)
        assert trackable_task.is_complete is False and trackable_task.is_pending is True

    client.start_task(WorkerTask(task_id=task_1.task_id))
    while not client.get_task(task_1.task_id).is_complete:
        time.sleep(0.1)
    client.start_task(WorkerTask(task_id=task_2.task_id))
    while not client.get_task(task_2.task_id).is_complete:
        time.sleep(0.1)
    task_by_completed = client.get_all_tasks()
    # https://github.com/DiamondLightSource/blueapi/issues/680
    # task_by_pending = client.get_tasks_by_status(TaskStatusEnum.COMPLETE)
    assert len(task_by_completed.tasks) == 2
    # Check if all the tasks are completed
    for task in task_by_completed.tasks:
        trackable_task = TypeAdapter(TrackableTask).validate_python(task)
        assert trackable_task.is_complete is True and trackable_task.is_pending is False

    client.clear_task(task_id=task_1.task_id)
    client.clear_task(task_id=task_2.task_id)


@disable_side_effects
def test_progress_with_stomp(
    client_with_stomp: BlueapiClient, task_definition: dict[str, Task]
):
    all_events: list[AnyEvent] = []

    def on_event(event: AnyEvent):
        all_events.append(event)

    client_with_stomp.run_task(task_definition["simple_plan"], on_event=on_event)
    assert isinstance(all_events[0], WorkerEvent) and all_events[0].task_status
    task_id = all_events[0].task_status.task_id
    assert all_events == [
        WorkerEvent(
            state=WorkerState.RUNNING,
            task_status=TaskStatus(
                task_id=task_id,
                task_complete=False,
                task_failed=False,
            ),
        ),
        WorkerEvent(
            state=WorkerState.IDLE,
            task_status=TaskStatus(
                task_id=task_id,
                task_complete=False,
                task_failed=False,
            ),
        ),
        WorkerEvent(
            state=WorkerState.IDLE,
            task_status=TaskStatus(
                task_id=task_id,
                task_complete=True,
                task_failed=False,
            ),
        ),
    ]


def test_get_current_state_of_environment(client: BlueapiClient):
    assert client.get_environment() == EnvironmentResponse(initialized=True)


@pytest.mark.xfail(
    reason="""
    client.reload_environment does not currently wait for the environment to fully
    reload This causes the test to fail intermittently.
    More details can be found in the related issue: https://github.com/DiamondLightSource/blueapi/issues/742.
    """
)
def test_delete_current_environment(client: BlueapiClient):
    client.reload_environment()

    # The client may return an initialized environment immediately after reload,
    # but the reload process takes time to fully complete. Adding a brief wait.
    time.sleep(1)

    @backoff.on_predicate(
        backoff.expo, lambda x: x != EnvironmentResponse(initialized=True), max_time=10
    )
    def wait_for_reload() -> EnvironmentResponse:
        return client.get_environment()

    # Wait for the environment to report as initialized,
    # retrying with exponential backoff
    assert wait_for_reload() == EnvironmentResponse(initialized=True)

    # The first successful response might be premature; wait briefly to ensure stability
    time.sleep(1)
    assert client.get_environment() == EnvironmentResponse(initialized=True)
