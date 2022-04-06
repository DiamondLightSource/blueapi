import json
from typing import Any, AsyncIterable, List, Mapping, Optional, TypeVar, Union

import aiohttp

T = TypeVar("T")

_Json = Union[List[Any], Mapping[str, Any]]


class RestClient:
    url: str

    def __init__(self, url: str) -> None:
        self.url = url

    async def get_abilities(self) -> _Json:
        return await self._get_json("/ability")

    async def run_plan(self, name: str, params: Mapping[str, Any]) -> None:
        await self._put_json(f"/run/{name}", params)

    async def get_plans(self) -> _Json:
        return await self._get_json("/plan")

    async def get_plan(self, name: str) -> _Json:
        return await self._get_json(f"/plan/{name}")

    async def subscribe_worker_events(self) -> AsyncIterable[_Json]:
        async for v in self._subscribe_json("/run/status"):
            yield v

    async def _get_json(self, path: str) -> _Json:
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url + path) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise IOError(f"Bad status on HTTP response: {resp}")

    async def _put_json(
        self, path: str, params: Optional[Mapping[str, Any]] = None
    ) -> _Json:
        async with aiohttp.ClientSession() as session:
            async with session.put(self.url + path, json=params or {}) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise IOError(f"Bad status on HTTP response: {resp}")

    async def _subscribe_json(self, path: str) -> AsyncIterable[Mapping[str, Any]]:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(self.url + path) as ws:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        yield json.loads(msg.data)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        raise IOError(f"Error from websocket: {msg}")
