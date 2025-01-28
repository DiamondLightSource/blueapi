import uuid
from multiprocessing.pool import Pool as PoolClass
from typing import Any, Generic, TypeVar
from unittest.mock import MagicMock, Mock, patch

import pytest
from observability_utils.tracing import (
    JsonObjectSpanExporter,
    asserting_span_exporter,
)
from ophyd import Callable
from pydantic import BaseModel, ValidationError

from blueapi.service import interface
from blueapi.service.model import EnvironmentResponse
from blueapi.service.runner import (
    InvalidRunnerStateError,
    RpcError,
    WorkerDispatcher,
    _safe_exception_message,
    import_and_run_function,
)


@pytest.fixture
def mock_subprocess() -> Mock:
    subprocess = Mock(spec=PoolClass)
    return subprocess


@pytest.fixture
def runner(mock_subprocess: Mock):
    return WorkerDispatcher(subprocess_factory=lambda: mock_subprocess)


@pytest.fixture
def started_runner(runner: WorkerDispatcher):
    runner.start()
    yield runner
    runner.stop()


def test_initialize(runner: WorkerDispatcher, mock_subprocess: Mock):
    mock_subprocess.apply.return_value = None

    assert runner.state.error_message is None
    assert not runner.state.initialized
    runner.start()

    assert runner.state.error_message is None
    assert runner.state.initialized

    # Run a single call to the runner for coverage of dispatch to subprocess
    mock_subprocess.apply.return_value = 123
    assert runner.run(interface.get_worker_state) == 123
    runner.stop()

    assert runner.state.error_message is None
    assert not runner.state.initialized


def test_reload(runner: WorkerDispatcher):
    runner.start()
    assert runner.state.initialized
    runner.reload()
    assert runner.state.initialized
    runner.stop()


def test_raises_if_used_before_started(runner: WorkerDispatcher):
    with pytest.raises(InvalidRunnerStateError):
        runner.run(interface.get_plans)


@pytest.mark.parametrize(
    "message",
    [
        None,
        "",
        "    ",
        "Intentional start_worker exception",
    ],
)
def test_using_safe_exception_message_copes_with_all_message_types_on_runner_setup(
    runner: WorkerDispatcher, mock_subprocess: Mock, message: str | None
):
    try:
        raise Exception() if message is None else Exception(message)
    except Exception as e:
        expected_state = EnvironmentResponse(
            environment_id=uuid.uuid4(),
            initialized=False,
            error_message=_safe_exception_message(e),
        )
    mock_subprocess.apply.side_effect = (
        Exception() if message is None else Exception(message)
    )

    # Calling reload here instead of start also indirectly tests
    # that stop() doesn't raise if there is no error message and the
    # runner is not yet initialised.
    runner.reload()
    state = runner.state
    expected_state.environment_id = state.environment_id
    assert state == expected_state


def start_worker_mock():
    yield SyntaxError("invalid syntax")
    yield None


@patch("blueapi.service.runner.Pool")
def test_can_reload_after_an_error(pool_mock: MagicMock):
    another_mock = MagicMock()
    pool_mock.return_value = another_mock

    # This test ensures the subprocess worker can be reloaded
    # after failing to initialise

    # all calls to subprocess (poll::apply) are mocked
    subprocess_calls_return_values = [
        SyntaxError("invalid code"),  # start_worker
        None,  # stop_worker
        None,  # start_worker
    ]

    another_mock.apply.side_effect = subprocess_calls_return_values

    runner = WorkerDispatcher()
    runner.start()
    current_env = runner.state.environment_id
    assert runner.state == EnvironmentResponse(
        environment_id=current_env,
        initialized=False,
        error_message="SyntaxError: invalid code",
    )

    runner.reload()
    new_env = runner.state.environment_id
    assert runner.state == EnvironmentResponse(
        environment_id=new_env, initialized=True, error_message=None
    )
    assert current_env != new_env


@patch("blueapi.service.runner.Pool")
def test_subprocess_enabled_by_default(pool_mock: MagicMock):
    runner = WorkerDispatcher()
    runner.start()
    pool_mock.assert_called_once()
    runner.stop()


def test_clear_message_for_anonymous_function(started_runner: WorkerDispatcher):
    non_fetchable_callable = MagicMock()

    with pytest.raises(
        RpcError,
        match="<MagicMock id='[0-9]+'> is anonymous, cannot be run in subprocess",
    ):
        started_runner.run(non_fetchable_callable)


def test_function_not_findable_on_subprocess():
    with pytest.raises(RpcError, match="unknown: No such function in subprocess API"):
        import_and_run_function("blueapi", "unknown", None, {})


def test_module_not_findable_on_subprocess():
    with pytest.raises(ModuleNotFoundError):
        import_and_run_function("unknown", "unknown", None, {})


def run_rpc_function(
    func: Callable[..., Any],
    expected_type: type[Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    import_and_run_function(
        func.__module__,
        func.__name__,
        expected_type,
        {},
        *args,
        **kwargs,
    )


def test_non_callable_excepts(started_runner: WorkerDispatcher):
    # Not a valid target on main or sub process
    from tests.unit_tests.core.fake_device_module import fetchable_non_callable

    with pytest.raises(
        RpcError,
        match="fetchable_non_callable: Object in subprocess is not a function",
    ):
        run_rpc_function(fetchable_non_callable, Mock)


def test_clear_message_for_wrong_return(started_runner: WorkerDispatcher):
    from tests.unit_tests.core.fake_device_module import wrong_return_type

    with pytest.raises(
        ValidationError,
        match="1 validation error for int",
    ):
        run_rpc_function(wrong_return_type, int)


T = TypeVar("T")


class SimpleModel(BaseModel):
    a: int
    b: str


class NestedModel(BaseModel):
    nested: SimpleModel
    c: bool


class GenericModel(BaseModel, Generic[T]):
    a: T
    b: str


def return_int() -> int:
    return 1


def return_str() -> str:
    return "hello"


def return_list() -> list[int]:
    return [1, 2, 3]


def return_dict() -> dict[str, int]:
    return {
        "test": 1,
        "other_test": 2,
    }


def return_simple_model() -> SimpleModel:
    return SimpleModel(a=1, b="hi")


def return_nested_model() -> NestedModel:
    return NestedModel(nested=return_simple_model(), c=False)


def return_unbound_generic_model() -> GenericModel:
    return GenericModel(a="foo", b="bar")


def return_bound_generic_model() -> GenericModel[int]:
    return GenericModel(a=1, b="hi")


def return_explicitly_bound_generic_model() -> GenericModel[int]:
    return GenericModel[int](a=1, b="hi")


@pytest.mark.parametrize(
    "rpc_function",
    [
        return_int,
        return_str,
        return_list,
        return_dict,
        return_simple_model,
        return_nested_model,
        return_unbound_generic_model,
        # https://github.com/pydantic/pydantic/issues/6870 return_bound_generic_model,
        return_explicitly_bound_generic_model,
    ],
)
def test_accepts_return_type(
    started_runner: WorkerDispatcher,
    rpc_function: Callable[[], Any],
):
    started_runner.run(rpc_function)


def test_run_span_ok(
    exporter: JsonObjectSpanExporter, started_runner: WorkerDispatcher
):
    with asserting_span_exporter(exporter, "run", "function", "args", "kwargs"):
        started_runner.run(interface.get_plans)
