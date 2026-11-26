import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from starlette.status import WS_1007_INVALID_FRAME_PAYLOAD_DATA, WS_1013_TRY_AGAIN_LATER

from blueapi.service import interface, protocol
from blueapi.service.authentication import Fedid
from blueapi.service.model import WorkerTask
from blueapi.service.protocol import (
    InvalidArgs,
    PlanNotFound,
    ServerBusy,
    Submit,
    Unauthorized,
    Update,
)
from blueapi.worker.event import WorkerEvent
from blueapi.worker.task import TaskParameterError
from blueapi.worker.worker_errors import WorkerBusyError

from .dependencies import Opa, Runner, get_passthrough_headers

LOGGER = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/run_plan")
async def run_plan(
    ws: WebSocket,
    runner: Runner,
    user: Fedid,
    opa: Opa,
):
    LOGGER.info("Starting WS plan as %s", user)
    await ws.accept()
    rq = await ws.receive_text()
    try:
        task_request = Submit.model_validate_json(rq)
    except ValidationError:
        LOGGER.info("Failed to deserialize request: %r", rq, exc_info=True)
        await ws.close(
            code=WS_1007_INVALID_FRAME_PAYLOAD_DATA, reason="Invalid Request"
        )
        return
    LOGGER.info("Plan request: %s", task_request)

    if opa:
        try:
            await opa.can_submit_task(task_request.task)
        except Exception as e:
            LOGGER.info(
                "User %s does not have permission to run task", user, exc_info=e
            )
            await ws.send_text(Unauthorized().model_dump_json())
            await ws.close(code=protocol.AUTHZ_ERROR, reason="Unauthorized")
            return

    try:
        task_id: str = runner.run(
            interface.submit_task, task_request.task, {"user": user}
        )
        LOGGER.info("Task ID: %s", task_id)
    except TaskParameterError as tpe:
        LOGGER.info("Plan args not valid: %s - %s", task_request, tpe)
        await ws.send_text(InvalidArgs.from_parameter_error(tpe).model_dump_json())
        await ws.close(code=protocol.INVALID_ARGS, reason="Invalid Args")
        return
    except KeyError as ke:
        LOGGER.info("Plan %r not recognised", ke.args[0])
        await ws.send_text(PlanNotFound(plan_name=ke.args[0]).model_dump_json())
        await ws.close(code=protocol.UNKNOWN_PLAN, reason="Unknown Plan")
        return

    try:
        with runner.event_pipe() as events:
            active_task = runner.run(interface.get_active_task)
            if active_task is not None and not active_task.is_complete:
                raise WorkerBusyError("Task already running")
            runner.run(
                interface.begin_task,
                task=WorkerTask(task_id=task_id),
                pass_through_headers=get_passthrough_headers(ws),
            )
            async for evt in events:
                if evt.task_id != task_id:
                    continue
                LOGGER.debug("Event: %s", evt)
                await ws.send_text(Update(data=evt).model_dump_json())
                if isinstance(evt, WorkerEvent) and evt.is_complete():
                    LOGGER.debug("End of stream")
                    break
    except WorkerBusyError:
        LOGGER.error("Worker was busy")
        await ws.send_text(ServerBusy().model_dump_json())
        await ws.close(code=WS_1013_TRY_AGAIN_LATER, reason="Worker busy")
    except WebSocketDisconnect:
        LOGGER.info("Client disconnected")
        runner.run(
            interface.cancel_active_task, failure=True, reason="Client disconnected"
        )
    else:
        LOGGER.info("Plan complete")
        await ws.close()
