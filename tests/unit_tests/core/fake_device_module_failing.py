from ophyd_async.core import LazyMock, StandardReadable
from ophyd_async.epics.motor import Motor


class TimingOutDevice(StandardReadable):
    async def connect(
        self,
        mock: bool | LazyMock = False,
        timeout: float = 1.0,
        force_reconnect: bool = False,
    ) -> None:
        raise TimeoutError("Connection timed out")


def failing_device() -> Motor:
    raise TimeoutError("FooBar")


def timing_out_device() -> TimingOutDevice:
    return TimingOutDevice()
