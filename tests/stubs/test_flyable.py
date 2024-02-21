import asyncio
from typing import Dict

import bluesky.plan_stubs as bps
import pytest
from bluesky.protocols import Collectable, Descriptor, Flyable
from ophyd_async.core import AsyncStatus

from blueapi.stubs.flyable import fly_and_collect


class DummyFlyer(Flyable, Collectable):
    def __init__(self, name: str) -> None:
        self._name = name
        self.has_flown = False

    @property
    def name(self) -> str:
        return self._name

    @AsyncStatus.wrap
    async def kickoff(self) -> None:
        self._fly_status = AsyncStatus(self._fly())

    async def _fly(self) -> None:
        self.has_flown = True
        await asyncio.sleep(0.1)

    def complete(self) -> AsyncStatus:
        return self._fly_status

    def describe_collect(self) -> Dict[str, Descriptor]:
        return {
            self.name: Descriptor(
                source="some:source", shape=[], dtype="array", external="STREAM:"
            )
        }


@pytest.fixture
def flyer() -> Flyable:
    return DummyFlyer("test")


@pytest.mark.asyncio
async def test_fly_and_collect(RE, flyer: DummyFlyer):
    def open_and_close_run_for_fly_and_collect():
        yield from bps.open_run()
        yield from fly_and_collect(
            flyer, flush_period=0.01, checkpoint_every_collect=True
        )
        yield from bps.close_run()

    RE(open_and_close_run_for_fly_and_collect())
    assert flyer.has_flown is True
