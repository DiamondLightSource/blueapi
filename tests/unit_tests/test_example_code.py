import importlib
import sys

import pytest

from blueapi.core.context import BlueskyContext

sys.path.insert(0, "tests/unit_tests/code_examples")


@pytest.mark.parametrize(
    "module_name,plan_names",
    [
        ("plan_module", ["my_plan"]),
        ("plan_docstrings", ["temp_pressure_snapshot"]),
        ("plan_metadata", ["pass_metadata"]),
        ("deferred_plans", ["temp_pressure_snapshot"]),
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
    context.with_dodal_module(module)

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
    context.with_plan_module(module)
    with pytest.raises(TypeError):
        context.plan_functions["demo"](**{"foo": 1, "bar": 2})
