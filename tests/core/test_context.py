from typing import Dict, List, Union

import pytest
from bluesky.protocols import Descriptor, Reading, SyncOrAsync
from ophyd.sim import SynAxis, SynGauss

from blueapi.core import (
    BlueskyContext,
    MsgGenerator,
    PlanGenerator,
    is_bluesky_compatible_device,
)

#
# Dummy plans
#


def has_no_params() -> MsgGenerator:  # type: ignore
    ...


def has_one_param(foo: int) -> MsgGenerator:  # type: ignore
    ...


def has_some_params(foo: int, bar: str) -> MsgGenerator:  # type: ignore
    ...


def has_typeless_param(foo) -> MsgGenerator:  # type: ignore
    ...


def has_typed_and_typeless_params(foo: int, bar) -> MsgGenerator:  # type: ignore
    ...


def has_typeless_params(foo, bar) -> MsgGenerator:  # type: ignore
    ...


#
# Dummy devices
#

SIM_MOTOR_NAME = "sim"
SIM_DET_NAME = "sim_det"


@pytest.fixture
def sim_motor() -> SynAxis:
    return SynAxis(name=SIM_MOTOR_NAME)


@pytest.fixture
def sim_detector(sim_motor: SynAxis) -> SynAxis:
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
    with pytest.raises(TypeError):
        empty_context.plan(plan)


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
