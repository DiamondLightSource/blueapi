from typing import Any, Generic, TypeVar
from unittest import mock
from unittest.mock import MagicMock, patch

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
)


@pytest.fixture
def local_runner():
    return WorkerDispatcher(use_subprocess=False)


@pytest.fixture
def runner():
    return WorkerDispatcher()


@pytest.fixture
def started_runner(runner: WorkerDispatcher):
    runner.start()
    yield runner
    runner.stop()


def test_initialize(runner: WorkerDispatcher):
    assert not runner.state.initialized
    runner.start()
    assert runner.state.initialized
    # Run a single call to the runner for coverage of dispatch to subprocess
    assert runner.run(interface.get_worker_state)
    runner.stop()
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


def test_error_on_runner_setup(local_runner: WorkerDispatcher):
    expected_state = EnvironmentResponse(
        initialized=False,
        error_message="Intentional start_worker exception",
    )

    with mock.patch(
        "blueapi.service.runner.setup",
        side_effect=Exception("Intentional start_worker exception"),
    ):
        # Calling reload here instead of start also indirectly
        # tests that stop() doesn't raise if there is no error message
        # and the runner is not yet initialised
        local_runner.reload()
        state = local_runner.state
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

    runner = WorkerDispatcher(use_subprocess=True)
    runner.start()

    assert runner.state == EnvironmentResponse(
        initialized=False, error_message="invalid code"
    )

    runner.reload()

    assert runner.state == EnvironmentResponse(initialized=True, error_message=None)


def test_function_not_findable_on_subprocess(started_runner: WorkerDispatcher):
    from tests.unit_tests.core.fake_device_module import fake_motor_y

    # Valid target on main but not sub process
    # Change in this process not reflected in subprocess
    fake_motor_y.__name__ = "not_exported"

    with pytest.raises(
        RpcError, match="not_exported: No such function in subprocess API"
    ):
        started_runner.run(fake_motor_y)


def test_non_callable_excepts_in_main_process(started_runner: WorkerDispatcher):
    # Not a valid target on main or sub process
    from tests.unit_tests.core.fake_device_module import fetchable_non_callable

    with pytest.raises(
        RpcError,
        match="<NonCallableMock id='[0-9]+'> is not Callable, "
        + "cannot be run in subprocess",
    ):
        started_runner.run(fetchable_non_callable)


def test_non_callable_excepts_in_sub_process(started_runner: WorkerDispatcher):
    # Valid target on main but finds non-callable in sub process
    from tests.unit_tests.core.fake_device_module import (
        fetchable_callable,
        fetchable_non_callable,
    )

    fetchable_callable.__name__ = fetchable_non_callable.__name__

    with pytest.raises(
        RpcError,
        match="fetchable_non_callable: Object in subprocess is not a function",
    ):
        started_runner.run(fetchable_callable)


def test_clear_message_for_anonymous_function(started_runner: WorkerDispatcher):
    non_fetchable_callable = MagicMock()

    with pytest.raises(
        RpcError,
        match="<MagicMock id='[0-9]+'> is anonymous, cannot be run in subprocess",
    ):
        started_runner.run(non_fetchable_callable)


def test_clear_message_for_wrong_return(started_runner: WorkerDispatcher):
    from tests.unit_tests.core.fake_device_module import wrong_return_type

    with pytest.raises(
        ValidationError,
        match="1 validation error for int",
    ):
        started_runner.run(wrong_return_type)


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
