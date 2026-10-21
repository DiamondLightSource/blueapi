import logging

import bluesky.plan_stubs as bps
from dodal.common import MsgGenerator

LOGGER = logging.getLogger(__name__)


def failing_plan() -> MsgGenerator:
    yield from bps.open_run()
    yield from bps.sleep(time="2")
    yield from bps.close_run()


def failing_plan_outside_run() -> MsgGenerator:
    yield from bps.open_run()
    yield from bps.sleep(time=2)
    yield from bps.close_run()
    raise Exception("Run closed but I failed")


def failing_stub() -> MsgGenerator:
    yield from bps.sleep(time="2")
    # raise Exception("Failed stub")


def not_a_plan() -> MsgGenerator:  # type:ignore
    print("I am not a plan")


def failing_not_a_plan() -> MsgGenerator:  # type:ignore
    print("I am not a plan")
    raise Exception("I have failed")
