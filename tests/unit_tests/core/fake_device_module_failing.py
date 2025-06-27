from ophyd_async.epics.motor import Motor


def failing_device() -> Motor:
    raise TimeoutError("FooBar")
