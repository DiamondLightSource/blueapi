from typing import Protocol

from blueapi.service.model import TaskRequest
from blueapi.worker.event import TaskStatus

from .event_bus import OnAnyEvent


class ClientProtocol(Protocol):
    def run_task(
        self,
        task: TaskRequest,
        on_event: OnAnyEvent | None = None,
        timeout: float | None = None,
    ) -> TaskStatus: ...

    @property
    def instrument_session(self) -> str: ...
