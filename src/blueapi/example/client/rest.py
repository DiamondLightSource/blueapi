from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping, Optional, Type, TypeVar, Union

import aiohttp

T = TypeVar("T")

_Json = Union[List[Any], Mapping[str, Any]]


@dataclass
class RestEndpointSettings:
    plans: str = "/plans"


class RestClient:
    url: str
    settings: RestEndpointSettings

    def __init__(
        self, url: str, settings: Optional[RestEndpointSettings] = None
    ) -> None:
        self.url = url
        self.settings = settings or RestEndpointSettings()

    async def get_plans(self) -> _Json:
        return await self._get_json(self.url + self.settings.plans)

    async def _get_json(self, url: str) -> _Json:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise IOError(f"Bad status on HTTP response: {resp}")
