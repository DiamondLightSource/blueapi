import asyncio
from abc import ABC, abstractmethod
from ctypes import Union
from dataclasses import dataclass
from tkinter.messagebox import NO
from tokenize import Single
from typing import (
    Any,
    Callable,
    Generator,
    Iterable,
    List,
    Optional,
    Protocol,
    Type,
    TypeVar,
    runtime_checkable,
)

from bluesky.utils import Msg

from .params import schema_for_func

PlanGenerator = Callable[..., Generator[Msg, Any, None]]


@dataclass
class Plan:
    name: str
    model: Type[Any]
    func: PlanGenerator


class BlueskyAppBase(ABC):
    @abstractmethod
    def plan(self, plan: Plan):
        ...

    @abstractmethod
    def run(self) -> None:
        ...

    @abstractmethod
    async def run_async(self) -> None:
        ...


class BlueskyApp:
    _plans: List[Plan]

    def plan(self, plan: PlanGenerator) -> PlanGenerator:
        schema = schema_for_func(plan)
        self._plans.append(Plan(plan.__name__, schema, plan))
        return plan

    def run(self) -> None:
        asyncio.run(self.run_async())

    async def run_async(self) -> None:
        ...
