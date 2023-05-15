from __future__ import annotations

import inspect
from typing import Dict, List, Type, Union

import pytest
from bluesky.protocols import Descriptor, Movable, Readable, Reading, SyncOrAsync
from ophyd import Component
from ophyd.sim import SynAxis, SynGauss
from pydantic import parse_obj_as

from blueapi.config import EnvironmentConfig, Source, SourceKind
from blueapi.core import (
    BlueskyContext,
    MsgGenerator,
    PlanGenerator,
    is_bluesky_compatible_device,
)
from blueapi.core.context import DefaultFactory

SIM_MOTOR_NAME = "sim"
ALT_MOTOR_NAME = "alt"
SIM_DET_NAME = "sim_det"


#
# Dummy plans
#


def has_no_params() -> MsgGenerator:  # type: ignore
    ...


def has_one_param(foo: int) -> MsgGenerator:  # type: ignore
    ...


def has_some_params(foo: int = 42, bar: str = "bar") -> MsgGenerator:  # type: ignore
    ...


def has_typeless_param(foo) -> MsgGenerator:  # type: ignore
    ...


def has_typed_and_typeless_params(foo: int, bar) -> MsgGenerator:  # type: ignore
    ...


def has_typeless_params(foo, bar) -> MsgGenerator:  # type: ignore
    ...


def has_default_reference(
    m: Movable = Component(Movable, SIM_MOTOR_NAME)
) -> MsgGenerator:
    yield from []


def has_default_nested_reference(
    m: list[Movable] = [Component(Movable, SIM_MOTOR_NAME)]
) -> MsgGenerator:
    yield from []


#
# Dummy devices
#


@pytest.fixture
def sim_motor() -> SynAxis:
    return SynAxis(name=SIM_MOTOR_NAME)


@pytest.fixture
def alt_motor() -> SynAxis:
    return SynAxis(name=ALT_MOTOR_NAME)


@pytest.fixture
def sim_detector(sim_motor: SynAxis) -> SynGauss:
    return SynGauss(
        name=SIM_DET_NAME,
        motor=sim_motor,
        motor_field=SIM_MOTOR_NAME,
        center=0.0,
        Imax=1,
        labels={"detectors"},
    )


@pytest.fixture
def empty_context() -> BlueskyContext:
    return BlueskyContext()


@pytest.fixture
def devicey_context(sim_motor: SynAxis, sim_detector: SynGauss) -> BlueskyContext:
    ctx = BlueskyContext()
    ctx.device(sim_motor)
    ctx.device(sim_detector)
    return ctx


class SomeConfigurable:
    def read_configuration(self) -> SyncOrAsync[Dict[str, Reading]]:  # type: ignore
        ...

    def describe_configuration(  # type: ignore
        self,
    ) -> SyncOrAsync[Dict[str, Descriptor]]:
        ...


@pytest.fixture
def some_configurable() -> SomeConfigurable:
    return SomeConfigurable()


@pytest.mark.parametrize("plan", [has_no_params, has_one_param, has_some_params])
def test_add_plan(empty_context: BlueskyContext, plan: PlanGenerator) -> None:
    empty_context.plan(plan)
    assert plan.__name__ in empty_context.plans


@pytest.mark.parametrize(
    "plan", [has_typeless_param, has_typed_and_typeless_params, has_typeless_params]
)
def test_add_invalid_plan(empty_context: BlueskyContext, plan: PlanGenerator) -> None:
    with pytest.raises(ValueError):
        empty_context.plan(plan)


def test_add_plan_from_module(empty_context: BlueskyContext) -> None:
    import tests.core.fake_plan_module as plan_module

    empty_context.with_plan_module(plan_module)
    assert {"scan"} == empty_context.plans.keys()


def test_add_named_device(empty_context: BlueskyContext, sim_motor: SynAxis) -> None:
    empty_context.device(sim_motor)
    assert empty_context.devices[SIM_MOTOR_NAME] is sim_motor


def test_add_nameless_device(
    empty_context: BlueskyContext, some_configurable: SomeConfigurable
) -> None:
    empty_context.device(some_configurable, "conf")
    assert empty_context.devices["conf"] is some_configurable


def test_add_nameless_device_without_override(
    empty_context: BlueskyContext,
    some_configurable: SomeConfigurable,
) -> None:
    with pytest.raises(KeyError):
        empty_context.device(some_configurable)


def test_override_device_name(
    empty_context: BlueskyContext, sim_motor: SynAxis
) -> None:
    empty_context.device(sim_motor, "foo")
    assert empty_context.devices["foo"] is sim_motor


def test_add_devices_from_module(empty_context: BlueskyContext) -> None:
    import tests.core.fake_device_module as device_module

    empty_context.with_device_module(device_module)
    assert {
        "motor_x",
        "motor_y",
        "motor_bundle_a",
        "motor_bundle_b",
    } == empty_context.devices.keys()


@pytest.mark.parametrize(
    "addr", ["sim", "sim_det", "sim.setpoint", ["sim"], ["sim", "setpoint"]]
)
def test_lookup_device(
    devicey_context: BlueskyContext, addr: Union[str, List[str]]
) -> None:
    device = devicey_context.find_device(addr)
    assert is_bluesky_compatible_device(device)


def test_lookup_nonexistant_device(devicey_context: BlueskyContext) -> None:
    assert devicey_context.find_device("foo") is None


def test_lookup_nonexistant_device_child(devicey_context: BlueskyContext) -> None:
    assert devicey_context.find_device("sim.foo") is None


def test_lookup_non_device(devicey_context: BlueskyContext) -> None:
    with pytest.raises(ValueError):
        devicey_context.find_device("sim.SUB_READBACK")


def test_add_non_plan(empty_context: BlueskyContext) -> None:
    with pytest.raises(TypeError):
        empty_context.plan("not a plan")  # type: ignore


def test_add_non_device(empty_context: BlueskyContext) -> None:
    with pytest.raises(TypeError):
        empty_context.device("not a device")  # type: ignore


def test_add_devices_and_plans_from_modules_with_config(
    empty_context: BlueskyContext,
) -> None:
    empty_context.with_config(
        EnvironmentConfig(
            sources=[
                Source(
                    kind=SourceKind.DEVICE_FUNCTIONS,
                    module="tests.core.fake_device_module",
                ),
                Source(
                    kind=SourceKind.PLAN_FUNCTIONS, module="tests.core.fake_plan_module"
                ),
            ]
        )
    )
    assert {
        "motor_x",
        "motor_y",
        "motor_bundle_a",
        "motor_bundle_b",
    } == empty_context.devices.keys()
    assert {"scan"} == empty_context.plans.keys()


def test_function_spec(empty_context: BlueskyContext) -> None:
    spec = empty_context._type_spec_for_function(has_some_params)
    assert spec["foo"][0] == int
    assert spec["foo"][1].default_factory == DefaultFactory(42)
    assert spec["bar"][0] == str
    assert spec["bar"][1].default_factory == DefaultFactory("bar")


def test_basic_type_conversion(empty_context: BlueskyContext) -> None:
    assert empty_context._convert_type(int) == int
    assert empty_context._convert_type(dict[str, int]) == dict[str, int]


def test_device_reference_cache(empty_context: BlueskyContext) -> None:
    assert empty_context._reference(Movable) is empty_context._reference(Movable)
    assert empty_context._reference(Movable) is not empty_context._reference(Readable)


def test_reference_type_conversion(empty_context: BlueskyContext) -> None:
    movable_ref: Type = empty_context._reference(Movable)
    assert empty_context._convert_type(Movable) == movable_ref
    assert (
        empty_context._convert_type(dict[Movable, list[tuple[int, Movable]]])
        == dict[movable_ref, list[tuple[int, movable_ref]]]  # type: ignore
    )


def test_default_device_reference(empty_context: BlueskyContext) -> None:
    def default_movable(mov: Movable = "demo") -> MsgGenerator:  # type: ignore
        ...

    spec = empty_context._type_spec_for_function(default_movable)
    movable_ref = empty_context._reference(Movable)
    assert spec["mov"][0] == movable_ref
    assert spec["mov"][1].default_factory == DefaultFactory("demo")


class Named:
    """Concrete implementation of a Bluesky protocol (HasName)"""

    @property
    def name(self) -> str:
        return "Concrete"


def test_concrete_type_conversion(empty_context: BlueskyContext) -> None:
    hasname_ref = empty_context._reference(Named)
    assert empty_context._convert_type(Named) == hasname_ref


def test_concrete_method_annotation(empty_context: BlueskyContext) -> None:
    hasname_ref = empty_context._reference(Named)

    def demo(named: Named) -> None:
        ...

    spec = empty_context._type_spec_for_function(demo)
    assert spec["named"][0] is hasname_ref
    assert spec["named"][1].default_factory is None


def test_str_default(
    empty_context: BlueskyContext, sim_motor: SynAxis, alt_motor: SynAxis
):
    movable_ref = empty_context._reference(Movable)
    empty_context.device(sim_motor)
    empty_context.device(alt_motor)
    empty_context.plan(has_default_reference)
    signature = inspect.signature(has_default_reference)

    spec = empty_context._type_spec_for_function(has_default_reference)
    assert spec["m"][0] is movable_ref
    assert spec["m"][1].default_factory() is signature.parameters["m"].default

    assert has_default_reference.__name__ in empty_context.plans
    model = empty_context.plans[has_default_reference.__name__].model
    assert parse_obj_as(model, {}).m is sim_motor  # type: ignore
    assert parse_obj_as(model, {"m": ALT_MOTOR_NAME}).m == alt_motor  # type: ignore


def test_nested_str_default(
    empty_context: BlueskyContext, sim_motor: SynAxis, alt_motor: SynAxis
):
    empty_context.device(sim_motor)
    empty_context.device(alt_motor)
    empty_context.plan(has_default_nested_reference)
    signature = inspect.signature(has_default_nested_reference)

    spec = empty_context._type_spec_for_function(has_default_nested_reference)
    assert spec["m"][1].default_factory() == signature.parameters["m"].default

    assert has_default_nested_reference.__name__ in empty_context.plans
    model = empty_context.plans[has_default_nested_reference.__name__].model
    assert parse_obj_as(model, {}).m == [sim_motor]  # type: ignore
    assert parse_obj_as(model, {"m": [ALT_MOTOR_NAME]}).m == [alt_motor]  # type: ignore
