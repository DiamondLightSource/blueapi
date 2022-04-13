import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Union

from apischema import deserializer, identity, serializer
from apischema.conversions import Conversion

from blueapi.core import (
    BlueskyContext,
    Plan,
    create_bluesky_protocol_conversions,
    nested_deserialize_with_overrides,
)


class TaskState(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    COMPLETE = "COMPLETE"


_COMPLETE_TASK_STATES = (TaskState.FAILED, TaskState.COMPLETE)


class Task(ABC):
    """
    Object that can run with a TaskContext
    """

    _union: Any = None

    # You can use __init_subclass__ to register new subclass automatically
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Deserializers stack directly as a Union
        deserializer(Conversion(identity, source=cls, target=Task))
        # Only Base serializer must be registered (and updated for each subclass) as
        # a Union, and not be inherited
        Task._union = cls if Task._union is None else Union[Task._union, cls]
        serializer(
            Conversion(identity, source=Task, target=Task._union, inherited=False)
        )

    @abstractmethod
    def do_task(self, ctx: BlueskyContext) -> None:
        """
        Perform the task using the context

        Args:
            ctx (TaskContext): Context for the task
        """
        ...


LOGGER = logging.getLogger(__name__)


@dataclass
class RunPlan(Task):
    """
    Task that will run a plan
    """

    name: str
    params: Mapping[str, Any] = field(default_factory=dict)
    # plan: Generator[Msg, None, Any]

    def do_task(self, ctx: BlueskyContext) -> None:
        LOGGER.info(f"Asked to run plan {self.name} with {self.params}")

        plan = ctx.plans[self.name]
        plan_function = ctx.plan_functions[self.name]
        sanitized_params = lookup_params(ctx, plan, self.params)
        plan_generator = plan_function(**sanitized_params)
        ctx.run_engine(plan_generator)


def lookup_params(
    ctx: BlueskyContext, plan: Plan, params: Mapping[str, Any]
) -> Mapping[str, Any]:
    overrides = list(
        create_bluesky_protocol_conversions(lambda name: ctx.abilities[name])
    )
    return nested_deserialize_with_overrides(plan.model, params, overrides).__dict__


@dataclass
class ActiveTask:
    name: str
    task: Task
    state: TaskState = field(default=TaskState.PENDING)

    def is_complete(self) -> bool:
        return self.state in _COMPLETE_TASK_STATES
