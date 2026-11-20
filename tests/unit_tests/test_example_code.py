import importlib
import sys
from typing import Any

import pytest
from ophyd_async.sim import SimMotor

from blueapi.core.context import BlueskyContext
from blueapi.worker.task import Task

sys.path.insert(0, "tests/unit_tests/code_examples")


@pytest.mark.parametrize(
    "module_name,plan_names",
    [
        ("plan_module", ["my_plan"]),
        ("plan_docstrings", ["temp_pressure_snapshot"]),
        ("plan_metadata", ["pass_metadata"]),
        ("deferred_plans", ["temp_pressure_snapshot"]),
        ("plan_argument_kinds", ["repeated_read"]),
        ("plan_optional_device", ["count_with_optional_monitor"]),
    ],
)
def test_example_plan_module_is_detectable(module_name: str, plan_names: list[str]):
    context = BlueskyContext()
    module = importlib.import_module(module_name)
    context.with_plan_module(module)

    assert list(context.plans.keys()) == plan_names


def test_example_device_module_is_detectable():
    module_name = "device_module"
    device_name = "oav"

    context = BlueskyContext()
    module = importlib.import_module(module_name)
    context.with_device_manager(module.devices)

    assert device_name in context.devices


def test_count_parameter_model_example_is_accurate():
    context = BlueskyContext()
    module = importlib.import_module("count_plan")
    context.with_plan_module(module)
    plan = context.plans["count"]
    from tests.unit_tests.code_examples.count_model import CountParameters

    assert plan.model.model_fields.keys() == CountParameters.model_fields.keys()


def test_invalid_plan_args_are_invalid():
    context = BlueskyContext()
    module = importlib.import_module("invalid_plan_args")
    with pytest.raises(
        ValueError, match="Type annotation is required for 'args' in 'demo'"
    ):
        context.with_plan_module(module)


def test_optional_device_example_is_passed_device_or_name():
    context = BlueskyContext()
    monitor = SimMotor("monitor")
    context.register_device(SimMotor("detector"))
    context.register_device(monitor)
    context.with_plan_module(importlib.import_module("plan_optional_device"))

    def monitor_passed_to_plan(name: str) -> Any:
        task = Task(
            name="count_with_optional_monitor",
            params={"detector": "detector", "monitor": name},
        )
        _, kwargs = task.prepare_params(context)
        return kwargs["monitor"]

    assert monitor_passed_to_plan("monitor") is monitor
    assert monitor_passed_to_plan("not_a_device") == "not_a_device"
