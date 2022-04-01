from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, TypeVar, Union

import aiohttp

T = TypeVar("T")

_Json = Union[List[Any], Mapping[str, Any]]


class RestClient:
    url: str

    def __init__(self, url: str) -> None:
        self.url = url

    async def run_plan(self, name: str, params: Mapping[str, Any]) -> None:
        await self._put_json(self.url + f"/plan/{name}/run", params)

    async def get_plans(self) -> _Json:
        return await self._get_json(self.url + "/plan")

    async def _get_json(self, url: str) -> _Json:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise IOError(f"Bad status on HTTP response: {resp}")

    async def _put_json(
        self, url: str, params: Optional[Mapping[str, Any]] = None
    ) -> _Json:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, json=params or {}) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise IOError(f"Bad status on HTTP response: {resp}")
