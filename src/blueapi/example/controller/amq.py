import threading
from typing import Any, Callable, List, Mapping, Optional, TypeVar, Union

from blueapi.messaging import MessageContext, MessagingApp
from blueapi.worker import TaskEvent

T = TypeVar("T")

_Json = Union[List[Any], Mapping[str, Any]]


class AmqClient:
    app: MessagingApp

    def __init__(self, app: MessagingApp) -> None:
        self.app = app

    def run_plan(
        self,
        name: str,
        params: Mapping[str, Any],
        on_event: Optional[Callable[[TaskEvent], None]] = None,
        timeout: Optional[float] = None,
    ) -> str:
        complete = threading.Event()

        def on_event_wrapper(ctx: MessageContext, event: TaskEvent) -> None:
            if on_event is not None:
                on_event(event)
            if event.task.is_complete():
                complete.set()

        self.app.subscribe("worker.event.task", on_event_wrapper)
        # self.app.send("worker.run", {"name": name, "params": params})
        task_id = self.app.send_and_recieve(
            "worker.run", {"name": name, "params": params}
        ).result(timeout=5.0)

        if timeout is not None:
            complete.wait(timeout)

        return task_id

    def get_plans(self) -> _Json:
        return self.app.send_and_recieve(
            "worker.plans", "", List[Mapping[str, Any]]
        ).result(5.0)

    def get_abilities(self) -> _Json:
        return self.app.send_and_recieve(
            "worker.abilities", "", List[Mapping[str, Any]]
        ).result(5.0)
