from abc import ABC, abstractmethod
from typing import Any, Mapping

from blueapi.core import Ability, AsyncEventStreamBase, Plan


class BlueskyControllerBase(ABC):
    """
    Object to control Bluesky, bridge between API and worker
    """

    @abstractmethod
    async def run_workers(self) -> None:
        ...

    @abstractmethod
    async def run_plan(self, __name: str, __params: Mapping[str, Any]) -> None:
        """
        Run a named plan with parameters

        Args:
            __name (str): The name of the plan to run
            __params (Mapping[str, Any]): The parameters for the plan in
                                          deserialized form
        """

        ...

    @property
    @abstractmethod
    def worker_events(self) -> AsyncEventStreamBase:
        ...

    @property
    @abstractmethod
    def plans(self) -> Mapping[str, Plan]:
        """
        Get a all plans that can be run

        Returns:
            Mapping[str, Plan]: Mapping of plans for quick lookup by name
        """

        ...

    @property
    @abstractmethod
    def abilities(self) -> Mapping[str, Ability]:
        ...
