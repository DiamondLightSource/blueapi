import inspect
import time
from asyncio import Queue
from collections.abc import Generator
from contextlib import nullcontext
from enum import StrEnum
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import TypeAdapter

from blueapi.client import BlueapiClient
from blueapi.client.event_bus import AnyEvent
from blueapi.client.rest import (
    BlueapiRestClient,
    BlueskyRemoteControlError,
    BlueskyRequestError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorisedAccessError,
    UnknownPlanError,
)
from blueapi.config import (
    ApplicationConfig,
    ConfigLoader,
    OIDCConfig,
)
from blueapi.core.bluesky_types import DataEvent
from blueapi.service.model import (
    DeviceResponse,
    PlanResponse,
    TaskRequest,
    TaskResponse,
    WorkerTask,
)
from blueapi.worker.event import (
    TaskResult,
    TaskStatus,
    WorkerEvent,
    WorkerState,
)
from blueapi.worker.task_worker import TrackableTask


class User(StrEnum):
    alice = "alice"
    bob = "bob"
    admin = "admin"


class NonAdminUser(StrEnum):
    alice = "alice"
    bob = "bob"


class AdminUser(StrEnum):
    admin = "admin"


ValidUser = User | NonAdminUser | AdminUser

# Below is the default authorized instrument session for Users
VALID_INSTRUMENT_SESSION: dict[ValidUser, str] = {
    User.alice: "cm12345-1",
    User.bob: "cm12345-2",
    User.admin: "cm12345-2",  # Added as a placeholder
}

CURRENT_NUMTRACKER_NUM = 43

_DATA_PATH = Path(__file__).parent


# These system tests are run in the "system_tests" CI job, they can also be run
# and debugged locally.
#
# 1. Spin up dummy versions of associated services
# (outside of devcontainer)
#
# git submodule init
# docker compose -f tests/system_tests/compose.yaml up -d
#
# 2. Spin up blueapi server (inside devcontainer)
#
# source tests/system_tests/.env
# export TILED_SINGLE_USER_API_KEY=foo
# blueapi -c tests/system_tests/config.yaml serve
#
# Note: You can login into blueapi using username: admin and password: admin
# 3. Run the system tests
# tox -e system-test
#
# 4. To tear down the associated services
# (outside of devcontainer)
#
# docker compose -f tests/system_tests/compose.yaml down

# This client will give tokens for alice


def load_config(path: Path) -> ApplicationConfig:
    loader = ConfigLoader(ApplicationConfig)
    loader.use_values_from_yaml(path)
    return loader.load()


@pytest.fixture
def user(request) -> ValidUser:
    return getattr(request, "param", User.alice)


@pytest.fixture
def instrument_session(request) -> str:
    return getattr(request, "param", VALID_INSTRUMENT_SESSION[User.alice])


@pytest.fixture
def small_task(user: ValidUser, instrument_session: str) -> TaskRequest:
    return TaskRequest(
        name="sleep",
        params={"time": 0.0},
        instrument_session=instrument_session
        if instrument_session
        else VALID_INSTRUMENT_SESSION[user],
    )


def small_task_2(user: ValidUser, instrument_session: str) -> TaskRequest:
    return TaskRequest(
        name="sleep",
        params={"time": 0.0},
        instrument_session=instrument_session
        if instrument_session
        else VALID_INSTRUMENT_SESSION[user],
    )


@pytest.fixture
def long_task(user: ValidUser, instrument_session: str | None = None) -> TaskRequest:
    return TaskRequest(
        name="sleep",
        params={"time": 1.0},
        instrument_session=instrument_session
        if instrument_session
        else VALID_INSTRUMENT_SESSION[user],
    )


def get_access_token(user: ValidUser) -> str:
    token_url = "http://localhost:8081/realms/master/protocol/openid-connect/token"
    response = requests.post(
        token_url,
        data={
            "client_id": "system-test-blueapi-" + user.value,
            "client_secret": "secret",
            "grant_type": "client_credentials",
        },
    )
    response.raise_for_status()
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def client_without_auth() -> Generator[BlueapiClient]:
    with patch(
        "blueapi.service.authentication.SessionManager.from_cache",
        return_value=None,
    ):
        yield BlueapiClient.from_config(config=ApplicationConfig())


def patch_session(user: ValidUser):
    mock_session_manager = MagicMock()
    mock_session_manager.get_valid_access_token.return_value = get_access_token(user)
    return patch(
        "blueapi.service.authentication.SessionManager.from_cache",
        return_value=mock_session_manager,
    )


@pytest.fixture
def client_with_stomp(user: ValidUser) -> Generator[BlueapiClient]:
    with patch_session(user):
        yield BlueapiClient.from_config(
            config=load_config(_DATA_PATH / "config-cli.yaml")
        )


@pytest.fixture
def client(user: ValidUser) -> Generator[BlueapiClient]:
    with patch_session(user):
        yield BlueapiClient.from_config(config=ApplicationConfig())


@pytest.fixture
def client_factory() -> dict[ValidUser, BlueapiClient]:
    users: dict[ValidUser, BlueapiClient] = {}
    for user in User:
        with patch_session(user):
            users[user] = BlueapiClient.from_config(config=ApplicationConfig())

    return users


@pytest.fixture(scope="module", autouse=True)
def wait_for_server(client_without_auth: BlueapiClient):
    for _ in range(20):
        try:
            _ = client_without_auth.oidc_config
            return
        except ServiceUnavailableError:
            ...
        time.sleep(0.5)
    raise TimeoutError("No connection to the blueapi server")


@pytest.fixture
def rest_client(client: BlueapiClient) -> BlueapiRestClient:
    return client._rest


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
def blueapi_rest_client_get_methods() -> list[str]:
    # Get a list of methods that take only one argument (self)
    return [
        name
        for name, method in BlueapiRestClient.__dict__.items()
        if not name.startswith("__")
        and callable(method)
        and len(params := inspect.signature(method).parameters) == 1
        and "self" in params
    ]


@pytest.fixture(autouse=True)
def clean_existing_tasks(rest_client: BlueapiRestClient):
    for task in rest_client.get_all_tasks().tasks:
        rest_client.clear_task(task.task_id)
    yield


@pytest.fixture(autouse=True, scope="module")
def reset_numtracker():
    server_config = load_config(Path(_DATA_PATH, "config.yaml"))
    nt_url = server_config.numtracker.url  # type: ignore - if numtracker is None we should fail
    requests.post(
        str(nt_url),
        json={
            "query": f"""mutation {{
              configure(instrument: "adsim",
                        config: {{directory: "/tmp/",
                            scan: "{{instrument}}-{{scan_number}}",
                            detector: "{{instrument}}-{{scan_number}}-{{detector}}",
                            scanNumber: {CURRENT_NUMTRACKER_NUM}}}) {{
                scanTemplate
              }}
            }}"""
        },
    ).raise_for_status()
    yield


def test_cannot_access_endpoints_without_authentication(
    client_without_auth: BlueapiClient, blueapi_rest_client_get_methods: list[str]
):
    blueapi_rest_client_get_methods.remove(
        "get_oidc_config"
    )  # get_oidc_config can be accessed without auth
    for get_method in blueapi_rest_client_get_methods:
        with pytest.raises(UnauthorisedAccessError, match=r"Not authenticated"):
            getattr(client_without_auth._rest, get_method)()


def test_can_get_oidc_config_without_auth(client_without_auth: BlueapiClient):
    assert client_without_auth.get_oidc_config() == OIDCConfig(
        issuer="http://localhost:8081/realms/master",
        client_id="ixx-cli-blueapi",
        client_audience="ixx-blueapi",
    )


def test_get_plans(rest_client: BlueapiRestClient, expected_plans: PlanResponse):
    retrieved_plans = rest_client.get_plans()
    retrieved_plans.plans.sort(key=lambda x: x.name)
    expected_plans.plans.sort(key=lambda x: x.name)

    assert retrieved_plans.model_dump() == expected_plans.model_dump()


def test_get_plans_by_name(client: BlueapiClient, expected_plans: PlanResponse):
    for plan in expected_plans.plans:
        assert client.plans[plan.name].model == plan


def test_get_non_existent_plan(rest_client: BlueapiRestClient):
    with pytest.raises(UnknownPlanError, match=r"Plan 'Not exists' not found"):
        rest_client.get_plan("Not exists")


def test_client_non_existent_plan(client: BlueapiClient):
    with pytest.raises(AttributeError, match="No plan named 'missing' available"):
        _ = client.plans.missing


def test_get_devices(rest_client: BlueapiRestClient, expected_devices: DeviceResponse):
    retrieved_devices = rest_client.get_devices()
    retrieved_devices.devices.sort(key=lambda x: x.name)
    expected_devices.devices.sort(key=lambda x: x.name)

    assert retrieved_devices == expected_devices


def test_get_device_by_name(
    rest_client: BlueapiRestClient, expected_devices: DeviceResponse
):
    for device in expected_devices.devices:
        assert rest_client.get_device(device.name) == device


def test_get_non_existent_device(rest_client: BlueapiRestClient):
    with pytest.raises(NotFoundError, match=r"Item not found"):
        rest_client.get_device("Not exists")


def test_client_non_existent_device(client: BlueapiClient):
    with pytest.raises(AttributeError, match="No device named 'missing' available"):
        _ = client.devices.missing


def test_create_task_and_delete_task_by_id(
    rest_client: BlueapiRestClient, small_task: TaskRequest
):
    create_task = rest_client.create_task(small_task)
    rest_client.clear_task(create_task.task_id)


def test_instrument_session_propagated(
    rest_client: BlueapiRestClient, small_task: TaskRequest
):
    response = rest_client.create_task(small_task)
    trackable_task = rest_client.get_task(response.task_id)
    assert trackable_task.task.metadata == {
        "user": User.alice.value,
        "instrument_session": VALID_INSTRUMENT_SESSION[User.alice],
        "tiled_access_tags": [
            '{"proposal": 12345, "visit": 1, "beamline": "adsim"}',
        ],
    }


def test_create_task_validation_error(rest_client: BlueapiRestClient):
    with pytest.raises(BlueskyRequestError, match="Internal Server Error"):
        rest_client.create_task(
            TaskRequest(
                name="Not-exists",
                params={"Not-exists": 0.0},
                instrument_session="Not-exists",
            )
        )


def test_get_all_tasks(
    rest_client: BlueapiRestClient, small_task: TaskRequest, long_task: TaskRequest
):
    created_tasks: list[TaskResponse] = []
    for task in [small_task, long_task]:
        created_task = rest_client.create_task(task)
        created_tasks.append(created_task)
    task_ids = [task.task_id for task in created_tasks]

    task_list = rest_client.get_all_tasks()
    for trackable_task in task_list.tasks:
        assert trackable_task.task_id in task_ids
        assert trackable_task.is_complete is False and trackable_task.is_pending is True

    for task_id in task_ids:
        rest_client.clear_task(task_id)


def test_get_task_by_id(rest_client: BlueapiRestClient, small_task: TaskRequest):
    created_task = rest_client.create_task(small_task)

    get_task = rest_client.get_task(created_task.task_id)
    assert (
        get_task.task_id == created_task.task_id
        and get_task.is_pending
        and not get_task.is_complete
        and len(get_task.errors) == 0
    )

    rest_client.clear_task(created_task.task_id)


def test_get_non_existent_task(rest_client: BlueapiRestClient):
    with pytest.raises(NotFoundError, match=r"Item not found"):
        rest_client.get_task("Not-exists")


def test_delete_non_existent_task(rest_client: BlueapiRestClient):
    with pytest.raises(NotFoundError, match=r"Item not found"):
        rest_client.clear_task("Not-exists")


def test_put_worker_task(rest_client: BlueapiRestClient, small_task: TaskRequest):
    created_task = rest_client.create_task(small_task)
    rest_client.update_worker_task(WorkerTask(task_id=created_task.task_id))
    active_task = rest_client.get_active_task()
    assert active_task.task_id == created_task.task_id
    rest_client.clear_task(created_task.task_id)


def test_put_worker_task_fails_if_not_idle(
    rest_client: BlueapiRestClient, small_task: TaskRequest, long_task: TaskRequest
):
    _small_task = rest_client.create_task(small_task)
    _long_task = rest_client.create_task(long_task)

    rest_client.update_worker_task(WorkerTask(task_id=_long_task.task_id))
    active_task = rest_client.get_active_task()
    assert active_task.task_id == _long_task.task_id

    with pytest.raises(BlueskyRemoteControlError) as exception:
        rest_client.update_worker_task(WorkerTask(task_id=_small_task.task_id))
    assert exception.value.args[0] == 409
    rest_client.cancel_current_task(WorkerState.ABORTING)
    rest_client.clear_task(_small_task.task_id)
    rest_client.clear_task(_long_task.task_id)


def test_get_worker_state(client: BlueapiClient):
    assert client.state == WorkerState.IDLE


def test_set_state_transition_error(client: BlueapiClient):
    with pytest.raises(BlueskyRemoteControlError) as exception:
        client.resume()
    assert "Cannot transition from IDLE to RUNNING" in exception.value.args[1]
    with pytest.raises(BlueskyRemoteControlError) as exception:
        client.pause()
    assert "Cannot transition from IDLE to PAUSED" in exception.value.args[1]


def test_get_task_by_status(rest_client: BlueapiRestClient, small_task: TaskRequest):
    task_1 = rest_client.create_task(small_task)
    task_2 = rest_client.create_task(small_task)
    task_by_pending = rest_client.get_all_tasks()
    # https://github.com/DiamondLightSource/blueapi/issues/680
    # task_by_pending = client.get_tasks_by_status(TaskStatusEnum.PENDING)
    assert len(task_by_pending.tasks) == 2
    # Check if all the tasks are pending
    for task in task_by_pending.tasks:
        trackable_task = TypeAdapter(TrackableTask).validate_python(task)
        assert trackable_task.is_complete is False and trackable_task.is_pending is True

    rest_client.update_worker_task(WorkerTask(task_id=task_1.task_id))
    while not rest_client.get_task(task_1.task_id).is_complete:
        time.sleep(0.1)
    rest_client.update_worker_task(WorkerTask(task_id=task_2.task_id))
    while not rest_client.get_task(task_2.task_id).is_complete:
        time.sleep(0.1)
    task_by_completed = rest_client.get_all_tasks()
    # https://github.com/DiamondLightSource/blueapi/issues/680
    # task_by_pending = client.get_tasks_by_status(TaskStatusEnum.COMPLETE)
    assert len(task_by_completed.tasks) == 2
    # Check if all the tasks are completed
    for task in task_by_completed.tasks:
        trackable_task = TypeAdapter(TrackableTask).validate_python(task)
        assert trackable_task.is_complete is True and trackable_task.is_pending is False

    rest_client.clear_task(task_id=task_1.task_id)
    rest_client.clear_task(task_id=task_2.task_id)


def test_progress_with_stomp(client_with_stomp: BlueapiClient, small_task: TaskRequest):
    all_events: list[AnyEvent] = []

    def on_event(event: AnyEvent):
        all_events.append(event)

    client_with_stomp.run_task(small_task, on_event=on_event)
    assert isinstance(all_events[0], WorkerEvent) and all_events[0].task_status
    task_id = all_events[0].task_status.task_id
    assert all_events == [
        WorkerEvent(
            state=WorkerState.RUNNING,
            task_status=TaskStatus(
                task_id=task_id,
                task_complete=False,
                task_failed=False,
                result=None,
            ),
        ),
        WorkerEvent(
            state=WorkerState.IDLE,
            task_status=TaskStatus(
                task_id=task_id,
                task_complete=False,
                task_failed=False,
                result=None,
            ),
        ),
        WorkerEvent(
            state=WorkerState.IDLE,
            task_status=TaskStatus(
                task_id=task_id,
                task_complete=True,
                task_failed=False,
                result=TaskResult(result=None, type="NoneType"),
            ),
        ),
    ]


def test_get_current_state_of_environment(client: BlueapiClient):
    assert client.environment.initialized


def test_delete_current_environment(client: BlueapiClient):
    old_env = client.environment
    client.reload_environment()
    new_env = client.environment
    assert new_env.initialized
    assert new_env.environment_id != old_env.environment_id
    assert new_env.error_message is None


@pytest.mark.parametrize(
    "task,scan_id,user",
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
                instrument_session=VALID_INSTRUMENT_SESSION[User.alice],
            ),
            CURRENT_NUMTRACKER_NUM + 1,
            User.alice,
        ),
        (
            TaskRequest(
                name="spec_scan",
                params={
                    "detectors": ["det"],
                    "spec": {
                        "outer": {
                            "axis": "stage.x",
                            "start": 0.0,
                            "stop": 10.0,
                            "num": 2,
                            "type": "Linspace",
                        },
                        "inner": {
                            "axis": "stage.theta",
                            "start": 5.0,
                            "stop": 15.0,
                            "num": 3,
                            "type": "Linspace",
                        },
                        "gap": True,
                        "type": "Product",
                    },
                },
                instrument_session=VALID_INSTRUMENT_SESSION[User.bob],
            ),
            CURRENT_NUMTRACKER_NUM + 2,
            User.bob,
        ),
    ],
)
def test_plan_runs(
    client_with_stomp: BlueapiClient, task: TaskRequest, scan_id: int, user: User
):
    resource = Queue(maxsize=1)
    start = Queue(maxsize=1)

    def on_event(event: AnyEvent) -> None:
        if isinstance(event, DataEvent):
            if event.name == "start":
                start.put_nowait(event.doc)
            if event.name == "stream_resource":
                resource.put_nowait(event.doc)

    final_event = client_with_stomp.run_task(task, on_event)
    assert isinstance(final_event.result, TaskResult)
    assert final_event.task_complete
    assert not final_event.task_failed

    start_doc = start.get_nowait()
    assert start_doc["scan_id"] == scan_id
    assert start_doc["instrument"] == "adsim"
    assert start_doc["instrument_session"] == VALID_INSTRUMENT_SESSION[user]
    assert start_doc["data_session_directory"] == "/tmp"
    assert start_doc["scan_file"] == f"adsim-{scan_id}"

    stream_resource = resource.get_nowait()
    assert stream_resource["run_start"] == start_doc["uid"]
    assert stream_resource["uri"] == f"file://localhost/tmp/adsim-{scan_id}-det.h5"

    tiled_url = f"http://localhost:8407/api/v1/metadata/{start_doc['uid']}"
    response = requests.get(
        tiled_url, headers={"authorization": "Bearer " + get_access_token(user)}
    )
    assert response.status_code == 200
    json = response.json()
    assert "data" in json
    assert "attributes" in json["data"]
    assert "metadata" in json["data"]["attributes"]
    assert "start" in json["data"]["attributes"]["metadata"]
    start_metadata = response.json()["data"]["attributes"]["metadata"]["start"]
    assert "instrument_session" in start_metadata
    assert start_metadata["instrument_session"] == VALID_INSTRUMENT_SESSION[user]
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
            instrument_session=VALID_INSTRUMENT_SESSION[User.alice],
        ),
    ],
)
def test_stub_runs(client_with_stomp: BlueapiClient, task: TaskRequest):
    final_event = client_with_stomp.run_task(task)
    assert isinstance(final_event.result, TaskResult)
    assert final_event.task_complete
    assert not final_event.task_failed


@pytest.mark.parametrize(
    "instrument_session,user,expectation",
    [
        (
            # bob cannot submit a task that alice is on
            VALID_INSTRUMENT_SESSION[User.alice],
            User.bob,
            pytest.raises(
                UnauthorisedAccessError, match="Not authorized to submit task"
            ),
        ),
        (
            # alice cannot submit a task that bob is on
            VALID_INSTRUMENT_SESSION[User.bob],
            User.alice,
            pytest.raises(
                UnauthorisedAccessError, match="Not authorized to submit task"
            ),
        ),
        (
            # alice can submit a task that alice is on
            VALID_INSTRUMENT_SESSION[User.alice],
            User.alice,
            nullcontext(),
        ),
        (
            # bob can submit a task that bob is on
            VALID_INSTRUMENT_SESSION[User.bob],
            User.bob,
            nullcontext(),
        ),
        (
            # admin can submit a task that bob is on
            VALID_INSTRUMENT_SESSION[User.bob],
            User.admin,
            nullcontext(),
        ),
        (
            # admin can submit a task that alice is on
            VALID_INSTRUMENT_SESSION[User.alice],
            User.admin,
            nullcontext(),
        ),
        (
            # admin still needs to put a valid instrument_session
            VALID_INSTRUMENT_SESSION[User.alice] + "3231232",
            User.admin,
            pytest.raises(
                UnauthorisedAccessError, match="Not authorized to submit task"
            ),
        ),
    ],
)
def test_submit_plan_authorization(
    client: BlueapiClient,
    small_task: TaskRequest,
    user: str,
    instrument_session: str,
    expectation,
):
    with expectation:
        client.create_task(small_task)


def test_user_can_only_get_their_own_task(client_factory):
    tasks = {}
    for user in NonAdminUser:
        tasks[user] = (
            client_factory[user]
            .create_task(small_task_2(user, VALID_INSTRUMENT_SESSION[user]))
            .task_id
        )

    for user in NonAdminUser:
        for task in client_factory[user].get_all_tasks().tasks:
            assert task.task.metadata["user"] == user.value
            assert tasks[user] == task.task_id


def test_admin_can_get_all_task(client_factory):
    tasks = {}
    for user in User:
        tasks[user] = (
            client_factory[user]
            .create_task(small_task_2(user, VALID_INSTRUMENT_SESSION[user]))
            .task_id
        )

    for user in AdminUser:
        all_tasks = {}
        for task in client_factory[user].get_all_tasks().tasks:
            all_tasks[task.task.metadata["user"]] = task.task_id
        assert tasks == all_tasks


def test_user_can_only_delete_their_own_task(client_factory):
    tasks = {}
    for user in NonAdminUser:
        tasks[user] = (
            client_factory[user]
            .create_task(small_task_2(user, VALID_INSTRUMENT_SESSION[user]))
            .task_id
        )

    # for user in NonAdminUser:
    #     with pytest.raises():
    #         client_factory[user].clear_task()

    for user in NonAdminUser:
        client_factory[user].clear_task(tasks[user])


def test_admin_can_delete_anytask(client_factory):
    tasks = {}
    for user in User:
        tasks[user] = (
            client_factory[user]
            .create_task(small_task_2(user, VALID_INSTRUMENT_SESSION[user]))
            .task_id
        )

    for task in tasks:
        client_factory[AdminUser.admin].clear_task(task)


def test_any_user_can_get_active_task(client_factory):
    task_id = (
        client_factory[AdminUser.admin]
        .create_and_start_task(
            small_task_2(AdminUser.admin, VALID_INSTRUMENT_SESSION[AdminUser.admin])
        )
        .task_id
    )

    for user in User:
        assert client_factory[user].get_active_task == task_id


def test_only_user_who_create_a_task_can_set_it_active_task(client_factory): ...


def test_admin_can_set_any_task_active_task(client_factory): ...


@pytest.mark.parametrize(
    "user",
    [
        User.bob,
        User.alice,
        User.admin,
    ],
)
def test_any_user_can_get_worker_state(client: BlueapiClient, user: User):
    assert client.get_state() == WorkerState.IDLE


def test_user_can_only_set_worker_state_if_its_their_task(): ...


def test_admin_can_set_state_for_any_task(): ...


# Regression test for #1480
def test_task_submission_after_invalid_task(client_with_stomp: BlueapiClient):
    with pytest.raises(NotFoundError):
        # This task hasn't been submitted so should return an error...
        client_with_stomp._rest.update_worker_task(WorkerTask(task_id="missing"))

    # ...but should leave the serve in a state where it can still run tasks
    res = client_with_stomp.run_task(
        TaskRequest(
            name="count",
            params={
                "detectors": [
                    "det",
                ],
            },
            instrument_session=VALID_INSTRUMENT_SESSION[User.alice],
        )
    )
    assert isinstance(res.result, TaskResult)
