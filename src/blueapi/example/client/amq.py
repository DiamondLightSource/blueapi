from typing import Any, List, Mapping, Optional, TypeVar, Union

import aiohttp

from blueapi.messaging import MessagingApp

T = TypeVar("T")

_Json = Union[List[Any], Mapping[str, Any]]


class AmqClient:
    app: MessagingApp

    def __init__(self, app: MessagingApp) -> None:
        self.app = app

    # async def get_abilities(self) -> _Json:
    #     return await self._get_json("/ability")

    def run_plan(self, name: str, params: Mapping[str, Any]) -> None:
        self.app.send("worker.run", {"name": name, "params": params})

    def get_plans(self) -> _Json:
        return self.app.send_and_recieve(
            "worker.plans", "", List[Mapping[str, Any]]
        ).result(5.0)
