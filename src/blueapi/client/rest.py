from typing import Any, Iterable, List, Mapping, Optional, Type, TypeVar

import aiohttp
from apischema import deserialize

from blueapi.core import BlueskyService, Plan
from blueapi.rest.controller import RestEndpointSettings

T = TypeVar("T")


class RestClient(BlueskyService):
    url: str
    settings: RestEndpointSettings

    def __init__(
        self, url: str, settings: Optional[RestEndpointSettings] = None
    ) -> None:
        self.url = url
        self.settings = settings or RestEndpointSettings()

    async def get_plans(self) -> Iterable[Plan]:
        return await self._get_object(self.url + self.settings.plans, List[Plan])

    async def run_plan(self, name: str, params: Mapping[str, Any]) -> None:
        await self._get_json(self.url + self.settings.run_plan)

    async def _get_object(self, url: str, target: Type[T]) -> T:
        return deserialize(await self._get_json(url), target)

    async def _get_json(self, url: str) -> Mapping[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise IOError(f"Bad status on HTTP response: {resp}")
