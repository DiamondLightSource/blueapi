from typing import Any, List, Mapping

import bluesky.plan_stubs as bps

from blueapi.core import BlueskyApp
from blueapi.rest import RestController

app = BlueskyApp()


@app.plan
def fake_experiment(points: List[float], metadata: Mapping[str, Any]):
    yield from bps.sleep(5)


app.control_with(RestController())
