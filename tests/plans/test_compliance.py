import inspect
from types import ModuleType
from typing import Any, List, Mapping, Optional, get_type_hints

import dodal.plans as plans
import dodal.stubs as stubs
from dodal.common import MsgGenerator, PlanGenerator


def is_bluesky_plan_generator(func: Any) -> bool:
    try:
        return get_type_hints(func).get("return") == MsgGenerator
    except TypeError:
        # get_type_hints fails on some objects (such as Union or Optional)
        return False


def get_all_available_generators(mod: ModuleType):
    def get_named_subset(names: List[str]):
        for name in names:
            yield getattr(mod, name)

    if "__export__" in mod.__dict__:
        yield from get_named_subset(getattr(mod, "__export__"))
    elif "__all__" in mod.__dict__:
        yield from get_named_subset(getattr(mod, "__all__"))
    else:
        for name, value in mod.__dict__.items():
            if not name.startswith("_"):
                yield value


def assert_hard_requirements(plan: PlanGenerator, signature: inspect.Signature):
    assert plan.__doc__ is not None, f"'{plan.__name__}' has no docstring"
    for parameter in signature.parameters.values():
        assert (
            parameter.kind is not parameter.VAR_POSITIONAL
            and parameter.kind is not parameter.VAR_KEYWORD
        ), f"'{plan.__name__}' has variadic arguments"


def assert_metadata_requirements(plan: PlanGenerator, signature: inspect.Signature):
    assert (
        "metadata" in signature.parameters
    ), f"'{plan.__name__}' does not allow metadata"
    metadata = signature.parameters["metadata"]
    assert (
        metadata.annotation == Optional[Mapping[str, Any]]
        and metadata.default is not inspect.Parameter.empty
    ), f"'{plan.__name__}' metadata is not optional"
    assert metadata.default is None, f"'{plan.__name__}' metadata default is mutable"


def test_plans_comply():
    for plan in get_all_available_generators(plans):
        if is_bluesky_plan_generator(plan):
            signature = inspect.Signature.from_callable(plan)
            assert_hard_requirements(plan, signature)
            assert_metadata_requirements(plan, signature)


def test_stubs_comply():
    for plan in get_all_available_generators(stubs):
        if is_bluesky_plan_generator(plan):
            signature = inspect.Signature.from_callable(plan)
            assert_hard_requirements(plan, signature)
            if "metadata" in signature.parameters:
                assert_metadata_requirements(plan, signature)
