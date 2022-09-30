from typing import Dict

import pytest
from bluesky.protocols import Descriptor, Reading, SyncOrAsync
from ophyd.sim import SynAxis

from blueapi.core import BlueskyContext, MsgGenerator, PlanGenerator

#
# Dummy plans
#


def has_no_params() -> MsgGenerator:
    ...


def has_one_param(foo: int) -> MsgGenerator:
    ...


def has_some_params(foo: int, bar: str) -> MsgGenerator:
    ...


def has_typeless_param(foo) -> MsgGenerator:
    ...


def has_typed_and_typeless_params(foo: int, bar) -> MsgGenerator:
    ...


def has_typeless_params(foo, bar) -> MsgGenerator:
    ...


#
# Dummy devices
#

SIM_MOTOR_NAME = "sim"


@pytest.fixture
def sim_motor() -> SynAxis:
    return SynAxis(name=SIM_MOTOR_NAME)


class SomeConfigurable:
    def read_configuration(self) -> SyncOrAsync[Dict[str, Reading]]:
        ...

    def describe_configuration(self) -> SyncOrAsync[Dict[str, Descriptor]]:
        ...


@pytest.fixture
def some_configurable() -> SomeConfigurable:
    return SomeConfigurable()


@pytest.mark.parametrize("plan", [has_no_params, has_one_param, has_some_params])
def test_add_plan(plan: PlanGenerator) -> None:
    ctx = BlueskyContext()
    ctx.plan(plan)
    assert plan.__name__ in ctx.plans


@pytest.mark.parametrize(
    "plan", [has_typeless_param, has_typed_and_typeless_params, has_typeless_params]
)
def test_add_invalid_plan(plan: PlanGenerator) -> None:
    ctx = BlueskyContext()
    with pytest.raises(TypeError):
        ctx.plan(plan)


def test_add_named_device(sim_motor: SynAxis) -> None:
    ctx = BlueskyContext()
    ctx.device(sim_motor)
    assert ctx.devices[SIM_MOTOR_NAME] is sim_motor


def test_add_nameless_device(some_configurable: SomeConfigurable) -> None:
    ctx = BlueskyContext()
    ctx.device(some_configurable, "conf")
    assert ctx.devices["conf"] is some_configurable


def test_add_nameless_device_without_override(
    some_configurable: SomeConfigurable,
) -> None:
    ctx = BlueskyContext()
    with pytest.raises(KeyError):
        ctx.device(some_configurable)


def test_override_device_name(sim_motor: SynAxis) -> None:
    ctx = BlueskyContext()
    ctx.device(sim_motor, "foo")
    assert ctx.devices["foo"] is sim_motor
