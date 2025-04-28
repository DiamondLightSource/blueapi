import uuid
from dataclasses import dataclass
from unittest.mock import ANY, MagicMock, Mock, patch

import pytest
from bluesky.protocols import Stoppable
from bluesky.utils import MsgGenerator
from bluesky_stomp.messaging import StompClient
from dodal.common.beamlines.beamline_utils import (
    clear_path_provider,
    get_path_provider,
    set_path_provider,
)
from ophyd.sim import SynAxis
from stomp.connect import StompConnection11 as Connection

from blueapi.client.numtracker import NumtrackerClient
from blueapi.config import (
    ApplicationConfig,
    EnvironmentConfig,
    MetadataConfig,
    NumtrackerConfig,
    OIDCConfig,
    ScratchConfig,
    StompConfig,
)
from blueapi.core.context import BlueskyContext
from blueapi.service import interface
from blueapi.service.model import (
    DeviceModel,
    PackageInfo,
    PlanModel,
    ProtocolInfo,
    PythonEnvironmentResponse,
    SourceInfo,
    WorkerTask,
)
from blueapi.utils.invalid_config_error import InvalidConfigError
from blueapi.utils.path_provider import StartDocumentPathProvider
from blueapi.worker.event import TaskStatusEnum, WorkerState
from blueapi.worker.task import Task
from blueapi.worker.task_worker import TrackableTask


@pytest.fixture
def mock_connection() -> Mock:
    return Mock(spec=Connection)


@pytest.fixture
def mock_stomp_client(mock_connection: Mock) -> StompClient:
    stomp_client = StompClient(conn=mock_connection)
    stomp_client.disconnect = MagicMock()
    return stomp_client


@pytest.fixture(autouse=True)
def ensure_worker_stopped():
    """This saves every test having to call this at the end.
    Additionally, without this the tests would hang in the case
    of an assertion error. The start_worker method is not managed by a fixture
    as some of the tests require it to be customised."""
    yield
    interface.teardown()


def my_plan() -> MsgGenerator:
    """My plan does cool stuff."""
    yield from {}


def my_second_plan(repeats: int) -> MsgGenerator:
    """Plan B."""
    yield from {}


@patch("blueapi.service.interface.context")
def test_get_plans(context_mock: MagicMock):
    context = BlueskyContext()
    context.register_plan(my_plan)
    context.register_plan(my_second_plan)
    context_mock.return_value = context

    assert interface.get_plans() == [
        PlanModel(
            name="my_plan",
            description="My plan does cool stuff.",
            schema={
                "title": "my_plan",
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
        PlanModel(
            name="my_second_plan",
            description="Plan B.",
            schema={
                "title": "my_second_plan",
                "type": "object",
                "properties": {"repeats": {"title": "Repeats", "type": "integer"}},
                "required": ["repeats"],
                "additionalProperties": False,
            },
        ),
    ]


@patch("blueapi.service.interface.context")
def test_get_plan(context_mock: MagicMock):
    context = BlueskyContext()
    context.register_plan(my_plan)
    context.register_plan(my_second_plan)
    context_mock.return_value = context

    assert interface.get_plan("my_plan") == PlanModel(
        name="my_plan",
        description="My plan does cool stuff.",
        schema={
            "title": "my_plan",
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    )

    with pytest.raises(KeyError):
        interface.get_plan("non_existing_plan")


@dataclass
class MyDevice(Stoppable):
    name: str

    def stop(self, success: bool = True) -> None:
        pass


@patch("blueapi.service.interface.context")
def test_get_devices(context_mock: MagicMock):
    context = BlueskyContext()
    context.register_device(MyDevice(name="my_device"))
    context.register_device(SynAxis(name="my_axis"))
    context_mock.return_value = context

    assert interface.get_devices() == [
        DeviceModel(name="my_device", protocols=[ProtocolInfo(name="Stoppable")]),
        DeviceModel(
            name="my_axis",
            protocols=[
                ProtocolInfo(name="Checkable"),
                ProtocolInfo(name="Movable"),
                ProtocolInfo(name="Pausable"),
                ProtocolInfo(name="Readable"),
                ProtocolInfo(name="Stageable"),
                ProtocolInfo(name="Stoppable"),
                ProtocolInfo(name="Subscribable"),
                ProtocolInfo(name="Configurable"),
                ProtocolInfo(name="Triggerable"),
            ],
        ),
    ]


@patch("blueapi.service.interface.context")
def test_get_device(context_mock: MagicMock):
    context = BlueskyContext()
    context.register_device(MyDevice(name="my_device"))
    context_mock.return_value = context

    assert interface.get_device("my_device") == DeviceModel(
        name="my_device", protocols=[ProtocolInfo(name="Stoppable")]
    )

    with pytest.raises(KeyError):
        assert interface.get_device("non_existing_device")


@patch("blueapi.service.interface.context")
def test_submit_task(context_mock: MagicMock):
    context = BlueskyContext()
    context.register_plan(my_plan)
    task = Task(name="my_plan")
    context_mock.return_value = context
    mock_uuid_value = "8dfbb9c2-7a15-47b6-bea8-b6b77c31d3d9"
    with patch.object(uuid, "uuid4") as uuid_mock:
        uuid_mock.return_value = uuid.UUID(mock_uuid_value)
        task_uuid = interface.submit_task(task)
    assert task_uuid == mock_uuid_value


@patch("blueapi.service.interface.context")
def test_clear_task(context_mock: MagicMock):
    context = BlueskyContext()
    context.register_plan(my_plan)
    task = Task(name="my_plan")
    context_mock.return_value = context
    mock_uuid_value = "3d858a62-b40a-400f-82af-8d2603a4e59a"
    with patch.object(uuid, "uuid4") as uuid_mock:
        uuid_mock.return_value = uuid.UUID(mock_uuid_value)
        interface.submit_task(task)

    clear_task_return = interface.clear_task(mock_uuid_value)
    assert clear_task_return == mock_uuid_value


@patch("blueapi.service.interface.TaskWorker.begin_task")
def test_begin_task(worker_mock: MagicMock):
    uuid_value = "350043fd-597e-41a7-9a92-5d5478232cf7"
    task = WorkerTask(task_id=uuid_value)
    returned_task = interface.begin_task(task)
    assert task == returned_task
    worker_mock.assert_called_once_with(uuid_value)


@patch("blueapi.service.interface.TaskWorker.begin_task")
def test_begin_task_no_task_id(worker_mock: MagicMock):
    task = WorkerTask(task_id=None)
    returned_task = interface.begin_task(task)
    assert task == returned_task
    worker_mock.assert_not_called()


@patch("blueapi.service.interface.TaskWorker.get_tasks_by_status")
def test_get_tasks_by_status(get_tasks_by_status_mock: MagicMock):
    pending_task1 = TrackableTask(task_id="0", task=None)
    pending_task2 = TrackableTask(task_id="1", task=None)
    running_task = TrackableTask(task_id="2", task=None)

    def mock_tasks_by_status(status: TaskStatusEnum) -> list[TrackableTask]:
        if status == TaskStatusEnum.PENDING:
            return [pending_task1, pending_task2]
        elif status == TaskStatusEnum.RUNNING:
            return [running_task]
        else:
            return []

    get_tasks_by_status_mock.side_effect = mock_tasks_by_status

    assert interface.get_tasks_by_status(TaskStatusEnum.PENDING) == [
        pending_task1,
        pending_task2,
    ]
    assert interface.get_tasks_by_status(TaskStatusEnum.RUNNING) == [running_task]
    assert interface.get_tasks_by_status(TaskStatusEnum.COMPLETE) == []


@patch("blueapi.service.interface._try_configure_numtracker")
@patch("blueapi.service.interface.TaskWorker.begin_task")
def test_begin_task_with_headers(worker_mock: MagicMock, mock_configure: MagicMock):
    uuid_value = "350043fd-597e-41a7-9a92-5d5478232cf7"
    task = WorkerTask(task_id=uuid_value)
    headers = {"a": "b"}

    returned_task = interface.begin_task(task, headers)
    mock_configure.assert_called_once_with(headers)

    assert task == returned_task
    worker_mock.assert_called_once_with(uuid_value)


def test_get_active_task():
    assert interface.get_active_task() is None


def test_get_worker_state():
    assert interface.get_worker_state() == WorkerState.IDLE


@patch("blueapi.service.interface.TaskWorker.pause")
def test_pause_worker(pause_worker_mock: MagicMock):
    interface.pause_worker(False)
    pause_worker_mock.assert_called_once_with(False)

    pause_worker_mock.reset_mock()
    interface.pause_worker(True)
    pause_worker_mock.assert_called_once_with(True)


@patch("blueapi.service.interface.TaskWorker.resume")
def test_resume_worker(resume_worker_mock: MagicMock):
    interface.resume_worker()
    resume_worker_mock.assert_called_once()


@patch("blueapi.service.interface.TaskWorker.cancel_active_task")
def test_cancel_active_task(cancel_active_task_mock: MagicMock):
    fail = True
    reason = "End of session"
    task_id = "789"
    cancel_active_task_mock.return_value = task_id
    assert interface.cancel_active_task(fail, reason) == task_id
    cancel_active_task_mock.assert_called_once_with(fail, reason)


@patch("blueapi.service.interface.TaskWorker.get_tasks")
def test_get_tasks(get_tasks_mock: MagicMock):
    tasks = [
        TrackableTask(task_id="0", task=None),
        TrackableTask(task_id="1", task=None),
        TrackableTask(task_id="2", task=None),
    ]
    get_tasks_mock.return_value = tasks

    assert interface.get_tasks() == tasks


@patch("blueapi.service.interface.context")
def test_get_task_by_id(context_mock: MagicMock):
    context = BlueskyContext()
    context.register_plan(my_plan)
    context_mock.return_value = context

    task_id = interface.submit_task(Task(name="my_plan"))

    assert interface.get_task_by_id(task_id) == TrackableTask.model_construct(
        task_id=task_id,
        request_id=ANY,
        task=Task(name="my_plan", params={}),
        is_complete=False,
        is_pending=True,
        errors=[],
    )


def test_get_oidc_config(oidc_config: OIDCConfig):
    interface.set_config(ApplicationConfig(oidc=oidc_config))
    assert interface.get_oidc_config() == oidc_config

    interface.teardown()


def test_stomp_config(mock_stomp_client: StompClient):
    with patch(
        "blueapi.service.interface.StompClient.for_broker",
        return_value=mock_stomp_client,
    ):
        interface.set_config(ApplicationConfig(stomp=StompConfig(enabled=True)))
        assert interface.stomp_client() is not None


def test_stomp_config_makes_no_client_when_disabled(mock_stomp_client: StompClient):
    with patch(
        "blueapi.service.interface.StompClient.for_broker",
        return_value=mock_stomp_client,
    ):
        interface.set_config(ApplicationConfig(stomp=StompConfig(enabled=False)))
        assert interface.stomp_client() is None


@patch("blueapi.cli.scratch._fetch_installed_packages_details")
def test_get_scratch_no_config(mock_fetch_installed_packages: Mock):
    interface.set_config(ApplicationConfig(scratch=None))
    mock_fetch_installed_packages.return_value = []
    assert interface.get_python_env() == PythonEnvironmentResponse()


@patch("blueapi.service.interface.get_python_environment")
def test_get_scratch_with_config(mock_get_env: MagicMock):
    scratch_config = ScratchConfig()
    interface.set_config(ApplicationConfig(scratch=scratch_config))
    mock_response = PythonEnvironmentResponse(
        installed_packages=[
            PackageInfo(
                name="foo",
                version="http://example.com/foo.git@adsad23123",
                source=SourceInfo.SCRATCH,
                location="/tmp/foo",
                is_dirty=False,
            )
        ],
        scratch_enabled=True,
    )
    mock_get_env.return_value = mock_response

    assert interface.get_python_env() == mock_response
    mock_get_env.assert_called_once_with(config=scratch_config, name=None, source=None)


def test_configure_numtracker():
    conf = ApplicationConfig(
        numtracker=NumtrackerConfig(url="https://numtracker-example.com/graphql"),
        env=EnvironmentConfig(
            metadata=MetadataConfig(instrument="p46", instrument_session="ab123")
        ),
    )
    interface.set_config(conf)
    headers = {"a": "b"}
    interface._try_configure_numtracker(headers)
    nt = interface.numtracker_client()

    assert isinstance(nt, NumtrackerClient)
    assert nt._headers == {"a": "b"}
    assert nt._url == "https://numtracker-example.com/graphql"

    interface.teardown()


def test_configure_numtracker_with_no_numtracker_config_fails():
    conf = ApplicationConfig(
        env=EnvironmentConfig(
            metadata=MetadataConfig(instrument="p46", instrument_session="ab123")
        ),
    )
    interface.set_config(conf)
    headers = {"a": "b"}
    interface._try_configure_numtracker(headers)
    nt = interface.numtracker_client()

    assert nt is None

    interface.teardown()


def test_configure_numtracker_with_no_metadata_fails():
    conf = ApplicationConfig(numtracker=NumtrackerConfig())
    interface.set_config(conf)
    headers = {"a": "b"}

    assert conf.env.metadata is None

    with pytest.raises(InvalidConfigError):
        interface._try_configure_numtracker(headers)

    interface.teardown()


def test_setup_without_numtracker_with_exisiting_provider():
    conf = ApplicationConfig()
    interface.set_config(conf)
    set_path_provider(Mock())

    interface.setup(conf)

    assert interface.config() is not None
    assert interface.worker() is not None

    clear_path_provider()
    interface.teardown()


def test_setup_without_numtracker_without_exisiting_provider_does_not_make_one():
    conf = ApplicationConfig()
    interface.set_config(conf)
    interface.setup(conf)

    assert interface.config() is not None
    assert interface.worker() is not None

    with pytest.raises(NameError):
        get_path_provider()

    interface.teardown()


def test_setup_with_numtracker_makes_start_document_provider():
    conf = ApplicationConfig(
        env=EnvironmentConfig(
            metadata=MetadataConfig(instrument="p46", instrument_session="ab123")
        ),
        numtracker=NumtrackerConfig(),
    )
    interface.set_config(conf)
    interface.setup(conf)

    path_provider = get_path_provider()

    assert isinstance(path_provider, StartDocumentPathProvider)
    assert interface.context().run_engine.scan_id_source == interface._update_scan_num

    clear_path_provider()
    interface.teardown()


def test_setup_with_numtracker_with_exisiting_provider_raises():
    conf = ApplicationConfig(
        env=EnvironmentConfig(
            metadata=MetadataConfig(instrument="p46", instrument_session="ab123")
        ),
        numtracker=NumtrackerConfig(),
    )
    interface.set_config(conf)
    set_path_provider(Mock())
    path_provider = get_path_provider()

    with pytest.raises(
        InvalidConfigError,
        match="A StartDocumentPathProvider has not been configured for numtracker"
        f"because a different path provider was already set: {path_provider}",
    ):
        interface.setup(conf)

    clear_path_provider()
    interface.teardown()


@patch("blueapi.client.numtracker.NumtrackerClient.create_scan")
def test_numtracker_create_scan_called_with_arguments_from_metadata(mock_create_scan):
    conf = ApplicationConfig(
        numtracker=NumtrackerConfig(url="https://numtracker-example.com/graphql"),
        env=EnvironmentConfig(
            metadata=MetadataConfig(instrument="p46", instrument_session="ab123")
        ),
    )
    interface.set_config(conf)
    ctx = interface.context()

    headers = {"a": "b"}
    interface._try_configure_numtracker(headers)
    interface._update_scan_num(ctx.run_engine.md)

    mock_create_scan.assert_called_once_with("ab123", "p46")

    interface.teardown()
