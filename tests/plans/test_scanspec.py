from asyncio import Future

import pytest
from bluesky import RunEngine
from ophyd.sim import Syn2DGauss, SynAxis, SynGauss
from scanspec.specs import Line, Spiral

from blueapi.plans.scanspec import scan


@pytest.fixture
def x() -> SynAxis:
    return SynAxis(name="x")


@pytest.fixture
def y() -> SynAxis:
    return SynAxis(name="y")


def capture_document_return_token(future: Future, run_engine: RunEngine, name) -> int:
    def set_result(_, doc):
        future.set_result(doc)

    return run_engine.subscribe(name=name, func=set_result)


def test_metadata_of_simple_spec(RE, x, event_loop):
    det = SynGauss(
        name="det",
        motor=x,
        motor_field=x.name,
        center=0.0,
        Imax=1,
        labels={"detectors"},
    )
    spec = Line(axis=x.name, start=1, stop=2, num=3)

    start_future = event_loop.create_future()
    tok = capture_document_return_token(start_future, RE, "start")
    RE(scan([det], {x.name: x}, spec))
    RE.unsubscribe(tok)

    start_document = start_future.result()
    plan_args = start_document["plan_args"]

    assert len(plan_args) == 3
    assert plan_args["detectors"] == [repr(det)]
    assert plan_args["spec"] == repr(spec)
    assert plan_args["axes_to_move"] == {
        x.name: repr(x),
    }

    assert start_document["motors"] == [x.name]
    assert start_document["detectors"] == [det.name]


def test_metadata_of_spiral_spec(RE, x, y, event_loop):
    det = Syn2DGauss(
        name="det",
        motor0=x,
        motor_field0=x.name,
        motor1=y,
        motor_field1=y.name,
        center=(0.0, 0.0),
        Imax=1,
        labels={"detectors"},
    )
    spec = Spiral.spaced(x.name, y.name, 0, 0, 5, 1)

    start_future = event_loop.create_future()
    tok = capture_document_return_token(start_future, RE, "start")
    RE(scan([det], {x.name: x, y.name: y}, spec))
    RE.unsubscribe(tok)

    start_document = start_future.result()
    plan_args = start_document["plan_args"]

    assert len(plan_args) == 3
    assert plan_args["detectors"] == [repr(det)]
    assert plan_args["spec"] == repr(spec)
    assert plan_args["axes_to_move"] == {x.name: repr(x), y.name: repr(y)}

    assert set(start_document["motors"]) == {
        x.name,
        y.name,
    }  # Order of motors in scan_nd not guaranteed
    assert start_document["detectors"] == [det.name]
