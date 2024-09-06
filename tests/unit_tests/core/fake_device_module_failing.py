from ophyd import EpicsMotor


def failing_device() -> EpicsMotor:
    raise TimeoutError("FooBar")
