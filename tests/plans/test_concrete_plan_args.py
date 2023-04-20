from typing import Any, Dict, Generator, List, Mapping, Optional

import pytest
from bluesky.protocols import (
    Descriptor,
    HasName,
    Movable,
    Readable,
    Reading,
    Status,
    SyncOrAsync,
)
from ophyd.sim import SynAxis
from scanspec.specs import Line, Spec

from blueapi.core import BlueskyContext, Device, MsgGenerator, PlanGenerator
from blueapi.worker.task import _lookup_params


@pytest.fixture
def context(det: HasName, x: HasName) -> Generator[BlueskyContext, None, None]:
    ctx = BlueskyContext()
    ctx.device(det)
    ctx.device(x)
    yield ctx


class AbstractNamedMovable(Movable, HasName):
    ...


class DelegatingNamedMovable(AbstractNamedMovable):
    def __init__(self, name: str):
        self.axis = SynAxis(name=name)

    @property
    def name(self) -> str:
        return self.axis.name

    def set(self, value) -> Status:
        return self.axis.set(value)


class FunctionalReadable(Readable):
    def foo(self) -> str:
        return "det"

    @property
    def name(self) -> str:
        return self.foo()

    def describe(self) -> SyncOrAsync[Dict[str, Descriptor]]:
        return {}

    def read(self) -> SyncOrAsync[Dict[str, Reading]]:
        return {}


@pytest.fixture
def x() -> Device:
    return DelegatingNamedMovable("x")


@pytest.fixture
def det() -> Device:
    return FunctionalReadable()


def protocol_plan(motor: Movable) -> MsgGenerator:  # type: ignore
    ...


def abstract_plan(motor: AbstractNamedMovable) -> MsgGenerator:  # type: ignore
    ...


def concrete_plan(motor: DelegatingNamedMovable) -> MsgGenerator:  # type: ignore
    ...


def scan(  # type: ignore
    detectors: List[Readable],
    axes_to_move: Mapping[str, Movable],
    spec: Spec[str],
    metadata: Optional[Mapping[str, Any]] = None,
) -> MsgGenerator:
    ...


def tightly_bound_scan(  # type: ignore
    detectors: List[FunctionalReadable],
    axes_to_move: Mapping[str, DelegatingNamedMovable],
    spec: Line[str],
    metadata: Optional[Mapping[str, Any]] = None,
) -> MsgGenerator:
    ...


@pytest.mark.parametrize("plan", [protocol_plan, abstract_plan, concrete_plan])
def test_simple_plan(context, plan: PlanGenerator, x: Device):
    context.plan(plan)
    assert plan.__name__ in context.plans
    bm = _lookup_params(context, context.plans[plan.__name__], {"motor": "x"})
    assert getattr(bm, "motor") == x


@pytest.mark.parametrize("plan", [scan, tightly_bound_scan])
def test_scan(context, plan: PlanGenerator, x, det):
    context.plan(plan)
    assert plan.__name__ in context.plans
    bm = _lookup_params(
        context,
        context.plans[plan.__name__],
        {
            "detectors": ["det"],
            "axes_to_move": {"x": "x"},
            "spec": Line(axis="x", start=1, stop=1, num=1).serialize(),
        },
    )
    assert getattr(bm, "detectors") == [det]
    assert getattr(bm, "axes_to_move") == {"x": x}
