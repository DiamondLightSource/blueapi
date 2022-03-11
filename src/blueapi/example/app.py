from typing import Any, List, Mapping

import bluesky.plan_stubs as bps

from blueapi.core import BlueskyApp
from blueapi.rest import RestController

app = BlueskyApp()


@app.plan
def sleep(time: float):
    yield from bps.sleep(5)


@app.plan
def move(motor: str, pos: float):
    yield from bps.mv(motor, pos)


app.control_with(RestController())
