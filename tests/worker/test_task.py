from unittest.mock import Mock

import pytest

from blueapi.core import BlueskyContext, MsgGenerator
from blueapi.worker import Task


def plan() -> MsgGenerator:
    return "foo"


def plan_with_params(param: str) -> MsgGenerator:
    return "foo" + param


def wrapper(plan: MsgGenerator) -> MsgGenerator:
    return plan + "baz"


@pytest.fixture
def context() -> BlueskyContext:
    ctx = BlueskyContext()
    ctx.plan(plan)
    ctx.plan(plan_with_params)
    ctx.plan(wrapper)
    ctx.run_engine = Mock()
    return ctx


def test_task_with_no_global_wrapper(context: BlueskyContext):
    task = Task(name="plan")
    task.do_task(context)
    context.run_engine.assert_called_once_with("foo")  # type: ignore


def test_task_with_wrapper(context: BlueskyContext):
    context.with_global_plan_wrapper("wrapper")
    task = Task(name="plan")
    task.do_task(context)
    context.run_engine.assert_called_once_with("foobaz")  # type: ignore


def test_task_with_params(context: BlueskyContext):
    task = Task(name="plan_with_params", params={"param": "bar"})
    task.do_task(context)
    context.run_engine.assert_called_once_with("foobar")  # type: ignore
