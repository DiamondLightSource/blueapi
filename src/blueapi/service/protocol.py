"""
The application level sub-protocol used to communicate between the server and
client when running plans via websockets
"""

# Client to server
# * Submit task
# * Pause
# * Resume
# * Abort
#
# Server to client
# * Plan not found
# * Args not valid
# * Server busy
# * Event update

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from blueapi.core.bluesky_types import DataEvent
from blueapi.service.model import TaskRequest
from blueapi.worker.event import ProgressEvent, WorkerEvent


class ArgumentError(BaseModel):
    loc: list[str | int]
    msg: str | None
    type: str | None
    input: Any


class Submit(BaseModel):
    kind: Literal["submit"] = "submit"
    task: TaskRequest


class Pause(BaseModel):
    kind: Literal["pause"] = "pause"


class Resume(BaseModel):
    kind: Literal["resume"] = "resume"


class Abort(BaseModel):
    kind: Literal["abort"] = "abort"
    reason: str | None = None


ControlRequest = TypeAdapter(
    Annotated[Submit | Pause | Resume | Abort, Field(discriminator="kind")]
)


class PlanNotFound(BaseModel):
    kind: Literal["plan_not_found"] = "plan_not_found"
    plan_name: str


class InvalidArgs(BaseModel):
    kind: Literal["invalid_args"] = "invalid_args"
    errors: list[ArgumentError]

    @classmethod
    def from_validation_error(cls, e: ValidationError) -> Self:
        errors = [
            ArgumentError(
                loc=["body", "params", *err.get("loc", [])],
                msg=err.get("msg", None),
                type=err.get("type", None),
                # Input is not listed as required but is useful to have if available
                input=err.get("input", None),
            )
            for err in e.errors()
        ]
        return cls(errors=errors)


class ServerBusy(BaseModel):
    kind: Literal["busy"] = "busy"


class Update(BaseModel):
    kind: Literal["update"] = "update"
    data: WorkerEvent | DataEvent | ProgressEvent


ControlResponse = TypeAdapter(
    Annotated[
        PlanNotFound | InvalidArgs | ServerBusy | Update, Field(discriminator="kind")
    ]
)
