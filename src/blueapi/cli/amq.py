import threading
from typing import Any, Callable, List, Mapping, Optional, TypeVar, Union

from blueapi.messaging import MessageContext, MessagingTemplate
from blueapi.service import PlanModel
from blueapi.service.model import DeviceModel
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
            if event.task.is_complete():
                complete.set()

        self.app.subscribe(
            self.app.destinations.topic("worker.event.task"), on_event_wrapper
        )
        # self.app.send("worker.run", {"name": name, "params": params})
        task_id = self.app.send_and_recieve(
            "worker.run", {"name": name, "params": params}
        ).result(timeout=5.0)

        if timeout is not None:
            complete.wait(timeout)

        return task_id

    def get_plans(self) -> List[PlanModel]:
        return self.app.send_and_recieve("worker.plans", "", List[PlanModel]).result(
            5.0
        )

    def get_devices(self) -> List[DeviceModel]:
        return self.app.send_and_recieve(
            "worker.devices", "", List[DeviceModel]
        ).result(5.0)
