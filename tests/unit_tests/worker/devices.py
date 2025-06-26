from ophyd_async.epics.motor import Motor


def motor() -> Motor:
    return Motor("FOO:")
