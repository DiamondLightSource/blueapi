import threading
from typing import Any, Callable, List, Mapping, Optional, TypeVar, Union

from blueapi.messaging import MessageContext, MessagingTemplate
from blueapi.service.model import (
    DeviceRequest,
    DeviceResponse,
    PlanRequest,
    PlanResponse,
    TaskResponse,
)
from blueapi.worker import TaskEvent

T = TypeVar("T")

_Json = Union[List[Any], Mapping[str, Any]]


class AmqClient:
    app: MessagingTemplate

    def __init__(self, app: MessagingTemplate) -> None:
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
            if event.is_task_terminated():
                complete.set()

        self.app.subscribe(
            self.app.destinations.topic("public.worker.event.task"), on_event_wrapper
        )
        # self.app.send("worker.run", {"name": name, "params": params})
        task_response = self.app.send_and_recieve(
            "worker.run", {"name": name, "params": params}, reply_type=TaskResponse
        ).result(5.0)
        task_id = task_response.task_name

        if timeout is not None:
            complete.wait(timeout)

        return task_id

    def get_plans(self) -> PlanResponse:
        return self.app.send_and_recieve(
            "worker.plans", PlanRequest(), PlanResponse
        ).result(5.0)

    def get_devices(self) -> DeviceResponse:
        return self.app.send_and_recieve(
            "worker.devices", DeviceRequest(), DeviceResponse
        ).result(5.0)
