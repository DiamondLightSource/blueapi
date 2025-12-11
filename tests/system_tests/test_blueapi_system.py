import inspect
import time
from asyncio import Queue
from pathlib import Path

import pytest
import requests
from bluesky_stomp.models import BasicAuthentication
from pydantic import TypeAdapter
from requests.exceptions import ConnectionError
from scanspec.specs import Line

from blueapi.client.client import (
    BlueapiClient,
    BlueskyRemoteControlError,
)
from blueapi.client.event_bus import AnyEvent
from blueapi.client.rest import UnknownPlanError
from blueapi.config import (
    ApplicationConfig,
    ConfigLoader,
    OIDCConfig,
    StompConfig,
)
from blueapi.core.bluesky_types import DataEvent
from blueapi.service.model import (
    DeviceResponse,
    PlanResponse,
    TaskRequest,
    TaskResponse,
    WorkerTask,
)
from blueapi.worker.event import TaskStatus, WorkerEvent, WorkerState
from blueapi.worker.task_worker import TrackableTask

FAKE_INSTRUMENT_SESSION = "cm12345-1"
CURRENT_NUMTRACKER_NUM = 43

_SIMPLE_TASK = TaskRequest(
    name="sleep",
    params={"time": 0.0},
    instrument_session=FAKE_INSTRUMENT_SESSION,
)
_LONG_TASK = TaskRequest(
    name="sleep",
    params={"time": 1.0},
    instrument_session=FAKE_INSTRUMENT_SESSION,
)

_DATA_PATH = Path(__file__).parent

_REQUIRES_AUTH_MESSAGE = """
Authentication credentials are required to run this test.
The test has been skipped because authentication is currently disabled.
For more details, see: https://github.com/DiamondLightSource/blueapi/issues/676.
To enable and execute these tests, set `REQUIRES_AUTH=1` and provide valid credentials.
"""


# These system tests are run in the "system_tests" CI job, they can also be run
# and debugged locally.
#
# 1. Spin up dummy versions of associated services
# (outside of devcontainer)
#
# git submodule init
# export TILED_SINGLE_USER_API_KEY=foo
# docker compose -f tests/system_tests/compose.yaml up -d
#
# 2. Spin up blueapi server (inside devcontainer)
#
# source tests/system_tests/.env
# export TILED_SINGLE_USER_API_KEY=foo
# blueapi -c tests/system_tests/config.yaml serve
#
# 3. Run the system tests
# tox -e system-test
#
# 4. To tear down the associated services
# (outside of devcontainer)
#
# docker compose -f tests/system_tests/compose.yaml down


@pytest.fixture
def client_without_auth(tmp_path: Path) -> BlueapiClient:
    return BlueapiClient.from_config(config=ApplicationConfig(auth_token_path=tmp_path))


@pytest.fixture
def client_with_stomp() -> BlueapiClient:
    return BlueapiClient.from_config(
        config=ApplicationConfig(
            stomp=StompConfig(
                enabled=True,
                auth=BasicAuthentication(username="guest", password="guest"),  # type: ignore
            )
        )
    )


@pytest.fixture(scope="module", autouse=True)
def wait_for_server():
    client = BlueapiClient.from_config(config=ApplicationConfig())

    for _ in range(20):
        try:
            client.get_environment()
            return
        except ConnectionError:
            ...
        time.sleep(0.5)
    raise TimeoutError("No connection to the blueapi server")


# This client will have auth enabled if it finds cached valid token
@pytest.fixture
def client() -> BlueapiClient:
    return BlueapiClient.from_config(config=ApplicationConfig())


@pytest.fixture
def expected_plans() -> PlanResponse:
    return TypeAdapter(PlanResponse).validate_json(
        (_DATA_PATH / "plans.json").read_text()
    )


@pytest.fixture
def expected_devices() -> DeviceResponse:
    return TypeAdapter(DeviceResponse).validate_json(
        (_DATA_PATH / "devices.json").read_text()
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


@pytest.fixture(autouse=True)
def clean_existing_tasks(client: BlueapiClient):
    for task in client.get_all_tasks().tasks:
        client.clear_task(task.task_id)
    yield


@pytest.fixture(scope="module")
def server_config() -> ApplicationConfig:
    loader = ConfigLoader(ApplicationConfig)
    loader.use_values_from_yaml(Path("tests", "system_tests", "config.yaml"))
    return loader.load()


@pytest.fixture(autouse=True, scope="module")
def reset_numtracker(server_config: ApplicationConfig):
    nt_url = server_config.numtracker.url  # type: ignore - if numtracker is None we should fail
    requests.post(
        str(nt_url),
        json={
            "query": """mutation {
              configure(instrument: "adsim",
                        config: {directory: "/tmp/",
                                 scan: "{instrument}-{scan_number}",
                                 detector: "{instrument}-{scan_number}-{detector}",
                                 scanNumber: 43}) {
                scanTemplate
              }
            }"""
        },
    ).raise_for_status()
    yield


@pytest.mark.xfail(reason=_REQUIRES_AUTH_MESSAGE)
def test_cannot_access_endpoints(
    client_without_auth: BlueapiClient, blueapi_client_get_methods: list[str]
):
    blueapi_client_get_methods.remove(
        "get_oidc_config"
    )  # get_oidc_config can be accessed without auth
    for get_method in blueapi_client_get_methods:
        with pytest.raises(BlueskyRemoteControlError, match=r"<Response \[401\]>"):
            getattr(client_without_auth, get_method)()


@pytest.mark.xfail(reason=_REQUIRES_AUTH_MESSAGE)
def test_can_get_oidc_config_without_auth(client_without_auth: BlueapiClient):
    assert client_without_auth.get_oidc_config() == OIDCConfig(
        well_known_url="https://example.com/realms/master/.well-known/openid-configuration",
        client_id="blueapi-cli",
    )


def test_get_plans(client: BlueapiClient, expected_plans: PlanResponse):
    retrieved_plans = client.get_plans()
    retrieved_plans.plans.sort(key=lambda x: x.name)
    expected_plans.plans.sort(key=lambda x: x.name)

    assert retrieved_plans.model_dump() == expected_plans.model_dump()


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


def test_create_task_and_delete_task_by_id(client: BlueapiClient):
    create_task = client.create_task(_SIMPLE_TASK)
    client.clear_task(create_task.task_id)


def test_instrument_session_propagated(client: BlueapiClient):
    response = client.create_task(_SIMPLE_TASK)
    trackable_task = client.get_task(response.task_id)
    assert trackable_task.task.metadata == {
        "instrument_session": FAKE_INSTRUMENT_SESSION,
        "tiled_access_tags": [
            '{"proposal": 12345, "visit": 1, "beamline": "adsim"}',
        ],
    }


def test_create_task_validation_error(client: BlueapiClient):
    with pytest.raises(UnknownPlanError):
        client.create_task(
            TaskRequest(
                name="Not-exists",
                params={"Not-exists": 0.0},
                instrument_session="Not-exists",
            )
        )


def test_get_all_tasks(client: BlueapiClient):
    created_tasks: list[TaskResponse] = []
    for task in [_SIMPLE_TASK, _LONG_TASK]:
        created_task = client.create_task(task)
        created_tasks.append(created_task)
    task_ids = [task.task_id for task in created_tasks]

    task_list = client.get_all_tasks()
    for trackable_task in task_list.tasks:
        assert trackable_task.task_id in task_ids
        assert trackable_task.is_complete is False and trackable_task.is_pending is True

    for task_id in task_ids:
        client.clear_task(task_id)


def test_get_task_by_id(client: BlueapiClient):
    created_task = client.create_task(_SIMPLE_TASK)

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


def test_put_worker_task(client: BlueapiClient):
    created_task = client.create_task(_SIMPLE_TASK)
    client.start_task(WorkerTask(task_id=created_task.task_id))
    active_task = client.get_active_task()
    assert active_task.task_id == created_task.task_id
    client.clear_task(created_task.task_id)


def test_put_worker_task_fails_if_not_idle(client: BlueapiClient):
    small_task = client.create_task(_SIMPLE_TASK)
    long_task = client.create_task(_LONG_TASK)

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


def test_set_state_transition_error(client: BlueapiClient):
    with pytest.raises(BlueskyRemoteControlError) as exception:
        client.resume()
    assert "<Response [400]>" in str(exception)
    with pytest.raises(BlueskyRemoteControlError) as exception:
        client.pause()
    assert "<Response [400]>" in str(exception)


def test_get_task_by_status(client: BlueapiClient):
    task_1 = client.create_task(_SIMPLE_TASK)
    task_2 = client.create_task(_SIMPLE_TASK)
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


def test_progress_with_stomp(client_with_stomp: BlueapiClient):
    all_events: list[AnyEvent] = []

    def on_event(event: AnyEvent):
        all_events.append(event)

    client_with_stomp.run_task(_SIMPLE_TASK, on_event=on_event)
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
    assert client.get_environment().initialized


def test_delete_current_environment(client: BlueapiClient):
    old_env = client.get_environment()
    client.reload_environment()
    new_env = client.get_environment()
    assert new_env.initialized
    assert new_env.environment_id != old_env.environment_id
    assert new_env.error_message is None


@pytest.mark.parametrize(
    "task,scan_id",
    [
        (
            TaskRequest(
                name="count",
                params={
                    "detectors": [
                        "det",
                    ],
                    "num": 5,
                },
                instrument_session="cm12345-1",
            ),
            CURRENT_NUMTRACKER_NUM + 1,
        ),
        (
            TaskRequest(
                name="spec_scan",
                params={
                    "detectors": [
                        "det",
                    ],
                    "spec": Line("stage.x", 0.0, 10.0, 2)
                    * Line("stage.theta", 5.0, 15.0, 3),
                },
                instrument_session="cm12345-1",
            ),
            CURRENT_NUMTRACKER_NUM + 2,
        ),
    ],
)
def test_plan_runs(client_with_stomp: BlueapiClient, task: TaskRequest, scan_id: int):
    resource = Queue(maxsize=1)
    start = Queue(maxsize=1)

    def on_event(event: AnyEvent) -> None:
        if isinstance(event, DataEvent):
            if event.name == "start":
                start.put_nowait(event.doc)
            if event.name == "stream_resource":
                resource.put_nowait(event.doc)

    final_event = client_with_stomp.run_task(task, on_event)
    assert final_event.is_complete() and not final_event.is_error()
    assert final_event.state is WorkerState.IDLE

    start_doc = start.get_nowait()
    assert start_doc["scan_id"] == scan_id
    assert start_doc["instrument"] == "adsim"
    assert start_doc["instrument_session"] == FAKE_INSTRUMENT_SESSION
    assert start_doc["data_session_directory"] == "/tmp"
    assert start_doc["scan_file"] == f"adsim-{scan_id}"

    stream_resource = resource.get_nowait()
    assert stream_resource["run_start"] == start_doc["uid"]
    assert stream_resource["uri"] == f"file://localhost/tmp/adsim-{scan_id}-det.h5"

    tiled_url = f"http://localhost:8407/api/v1/metadata/{start_doc['uid']}"
    response = requests.get(tiled_url)
    assert response.status_code == 200
    json = response.json()
    assert "data" in json
    assert "attributes" in json["data"]
    assert "metadata" in json["data"]["attributes"]
    assert "start" in json["data"]["attributes"]["metadata"]
    start_metadata = response.json()["data"]["attributes"]["metadata"]["start"]
    assert "instrument_session" in start_metadata
    assert start_metadata["instrument_session"] == "cm12345-1"
    assert "scan_id" in start_metadata
    assert start_metadata["scan_id"] == scan_id
    assert "detectors" in start_metadata
    assert "det" in start_metadata["detectors"]


@pytest.mark.parametrize(
    "task",
    [
        TaskRequest(
            name="set_absolute",
            params={
                "movable": "stage.x",
                "value": "4.0",
            },
            instrument_session="cm12345-1",
        ),
    ],
)
def test_stub_runs(client_with_stomp: BlueapiClient, task: TaskRequest):
    final_event = client_with_stomp.run_task(task)
    assert final_event.is_complete() and not final_event.is_error()
    assert final_event.state is WorkerState.IDLE
