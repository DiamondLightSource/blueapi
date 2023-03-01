from ophyd.sim import Syn2DGauss, SynGauss, SynSignal

from blueapi.plans import *  # noqa: F401, F403

from .simmotor import BrokenSynAxis, SynAxisWithMotionEvents

x = SynAxisWithMotionEvents(name="x", delay=1.0, events_per_move=8)
y = SynAxisWithMotionEvents(name="y", delay=3.0, events_per_move=24)
z = SynAxisWithMotionEvents(name="z", delay=2.0, events_per_move=16)
theta = SynAxisWithMotionEvents(
    name="theta", delay=0.2, events_per_move=12, egu="degrees"
)
x_err = BrokenSynAxis(name="x_err", timeout=1.0)
sample_pressure = SynAxisWithMotionEvents(
    name="sample_pressure", delay=30.0, events_per_move=128, egu="MPa", value=0.101
)
sample_temperature = SynSignal(
    func=lambda: ((x.position + y.position + z.position) / 1000.0) + 20.0,
    name="sample_temperature",
)
image_det = Syn2DGauss(
    name="image_det",
    motor0=x,
    motor_field0="x",
    motor1=y,
    motor_field1="y",
    center=(0, 0),
    Imax=1,
    labels={"detectors"},
)
current_det = SynGauss(
    name="current_det",
    motor=x,
    motor_field="x",
    center=0.0,
    Imax=1,
    labels={"detectors"},
)
