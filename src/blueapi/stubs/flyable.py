import time
from typing import Protocol, runtime_checkable

import bluesky.plan_stubs as bps
from bluesky.protocols import Collectable, Flyable
from dodal.common import MsgGenerator, group_uuid


@runtime_checkable
class FlyableCollectable(Flyable, Collectable, Protocol):
    """
    A Device which implements both the Flyable and Collectable protocols.
    i.e., a device which can be set off, then polled repeatedly to construct documents
    with the data it has collected so far. A typical pattern for "hardware" scans.
    """


def fly_and_collect(
    flyer: FlyableCollectable,
    flush_period: float = 0.5,
    checkpoint_every_collect: bool = False,
    stream_name: str = "primary",
    timeout: float = 7_200,  # 2 hours
) -> MsgGenerator:
    """Fly and collect a flyer, waiting for collect to finish with a period.
    flyer.kickoff and complete are called, which starts the fly scanning process.
    bps.wait is called, which finishes after each flush period and then repeats, until
    complete finishes. At this point, bps.collect is called to gather the documents
    produced.
    For some flyers, this plan will need to be called in succession in order to, for
    example, set up a flyer to send triggers multiple times and collect data. For such
    a use case, this plan can be setup to checkpoint for each collect.
    Note: this plan must be wrapped with calls to open and close run, and the flyer
    must implement the Collectable protocol. See tests/stubs/test_flyables for an
    example.
    Args:
        flyer (FlyableCollectable): ophyd-async device which implements
            Flyable and Collectable.
        flush_period (float): How often to check if flyer.complete has finished in
            seconds. Default 0.5
        checkpoint_every_collect (bool): whether or not to checkpoint after
            flyer.collect has been called. Default False.
        stream_name (str): name of the stream to collect from. Default "primary".
        timeout (float): total time allowed for this stub before timing out in seconds.
            Default 7,200 (2 hours).
    Returns:
        MsgGenerator: Plan
    Yields:
        Iterator[MsgGenerator]: Bluesky messages
    """
    yield from bps.kickoff(flyer)
    complete_group = group_uuid("complete")
    yield from bps.complete(flyer, group=complete_group)
    start_time = time.time()
    done = False

    while not done:
        if time.time() - start_time < timeout:
            try:
                yield from bps.wait(group=complete_group, timeout=flush_period)
            except TimeoutError:
                pass
            else:
                done = True
            yield from bps.collect(
                flyer, stream=True, return_payload=False, name=stream_name
            )
            if checkpoint_every_collect:
                yield from bps.checkpoint()
        else:
            raise TimeoutError("fly_and_collect took longer than {timeout} to complete")
