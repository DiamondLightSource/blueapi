from typing import Any, List, Mapping, TypeVar, Union

import aiohttp

T = TypeVar("T")

_Json = Union[List[Any], Mapping[str, Any]]


class RestClient:
    url: str

    def __init__(self, url: str) -> None:
        self.url = url

    async def get_plans(self) -> _Json:
        return await self._get_json(self.url + "/plans")

    async def get_abilities(self) -> _Json:
        return await self._get_json(self.url + "/abilities")

    async def _get_json(self, url: str) -> _Json:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise IOError(f"Bad status on HTTP response: {resp}")
