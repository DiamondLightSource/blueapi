import json
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from super_state_machine.errors import TransitionError

from blueapi.config import ApplicationConfig
from blueapi.worker import Task, TrackableTask, WorkerState
from blueapi.worker.event import TaskStatusEnum

from .handler_base import BlueskyHandler
from .model import (
    DeviceModel,
    DeviceResponse,
    EnvironmentResponse,
    PlanModel,
    PlanResponse,
    StateChangeRequest,
    TaskResponse,
    TasksListResponse,
    WorkerTask,
)
from .subprocess_handler import SubprocessHandler

REST_API_VERSION = "0.0.5"

HANDLER: BlueskyHandler | None = None

print("Current working directory:", os.getcwd())
templates = Jinja2Templates(directory="templates")
print("templates", templates)


def get_handler() -> BlueskyHandler:
    if HANDLER is None:
        raise ValueError()
    return HANDLER


def setup_handler(config: ApplicationConfig | None = None):
    global HANDLER
    handler = SubprocessHandler(config)
    handler.start()

    HANDLER = handler


def teardown_handler():
    global HANDLER
    if HANDLER is None:
        return
    HANDLER.stop()
    HANDLER = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    config: ApplicationConfig = app.state.config
    setup_handler(config)
    yield
    teardown_handler()


app = FastAPI(
    docs_url="/docs",
    on_shutdown=[teardown_handler],
    title="BlueAPI Control",
    lifespan=lifespan,
    version=REST_API_VERSION,
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("landing_page.html", {"request": request})


@app.exception_handler(KeyError)
async def on_key_error_404(_: Request, __: KeyError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Item not found"},
    )


@app.get("/environment", response_model=EnvironmentResponse)
def get_environment(
    handler: BlueskyHandler = Depends(get_handler),
) -> EnvironmentResponse:
    """Get the current state of the environment, i.e. initialization state."""
    return handler.state


@app.delete("/environment", response_model=EnvironmentResponse)
async def delete_environment(
    background_tasks: BackgroundTasks,
    handler: BlueskyHandler = Depends(get_handler),
) -> EnvironmentResponse:
    """Delete the current environment, causing internal components to be reloaded."""

    def restart_handler(handler: BlueskyHandler):
        handler.stop()
        handler.start()

    if handler.state.initialized or handler.state.error_message is not None:
        background_tasks.add_task(restart_handler, handler)
    return EnvironmentResponse(initialized=False)


@app.get("/plans", response_model=PlanResponse)
def get_plans(
    request: Request,
    accept: Optional[str] = Header(None),
    handler: BlueskyHandler = Depends(get_handler),
):
    """Retrieve information about all available plans."""
    if "text/html" in accept:
        return templates.TemplateResponse(
            "plans.html", {"request": request, "plans": handler.plans}
        )
    return PlanResponse(plans=handler.plans)


@app.get(
    "/plans/{name}",
    response_model=PlanModel,
)
def get_plan_by_name(
    request: Request,
    name: str,
    handler: BlueskyHandler = Depends(get_handler),
    accept: Optional[str] = Header(None),
):
    """Retrieve information about a plan by its (unique) name."""
    try:
        plan = handler.get_plan(name)
        if "text/html" in accept:
            if isinstance(plan.parameter_schema, str):
                plan.parameter_schema = json.loads(plan.parameter_schema)
            return templates.TemplateResponse(
                "plan_details.html", {"request": request, "plan": plan}
            )
        else:
            return plan
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {name} not found",
        )


@app.get("/devices", response_model=DeviceResponse)
def get_devices(
    request: Request,
    accept: Optional[str] = Header(None),
    handler: BlueskyHandler = Depends(get_handler),
):
    """Retrieve information about all available devices."""
    devices = handler.devices
    if "text/html" in accept:
        return templates.TemplateResponse(
            "devices.html", {"request": request, "devices": devices}
        )
    return DeviceResponse(devices=devices)


@app.get(
    "/devices/{name}",
    response_model=DeviceModel,
)
def get_device_by_name(
    request: Request,
    name: str,
    handler: BlueskyHandler = Depends(get_handler),
    accept: Optional[str] = Header(None),
):
    """Retrieve information about a devices by its (unique) name."""
    try:
        device = handler.get_device(name)
        if "text/html" in accept:
            return templates.TemplateResponse(
                "device_details.html", {"request": request, "device": device}
            )
        return device
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {name} not found",
        )


example_task = Task(name="count", params={"detectors": ["x"]})


async def parse_task(
    request: Request, handler: BlueskyHandler = Depends(get_handler)
) -> Task:
    # the first branch is if it's a form submission
    if request.headers.get("Content-Type") == "application/x-www-form-urlencoded":
        form_data = await request.form()
        try:
            # Assuming `Task` can be created from form data dictionary
            return Task(name=form_data["name"], params=dict(form_data))
        except ValidationError as e:
            raise HTTPException(status_code=400, detail="Invalid task data from form.")
    else:
        # Assuming JSON Body
        try:
            return await request.json()
        except ValidationError as e:
            raise HTTPException(status_code=400, detail="Invalid JSON task data.")


@app.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_task(
    request: Request,
    response: Response,
    task: Task = Depends(parse_task),
    handler: BlueskyHandler = Depends(get_handler),
):
    """Submit a task to the worker."""
    try:
        plan_model = handler.get_plan(task.name)
        task_id: str = handler.submit_task(task)
        response.headers["Location"] = f"{request.url}/{task_id}"
        return TaskResponse(task_id=task_id)
    except ValidationError as e:
        errors = e.errors()
        formatted_errors = "; ".join(
            [f"{err['loc'][0]}: {err['msg']}" for err in errors]
        )
        error_detail_response = f"""
        Input validation failed: {formatted_errors},
        suppplied params {task.params},
        do not match the expected params: {plan_model.parameter_schema}
        """
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_detail_response,
        ) from e


@app.delete("/tasks/{task_id}", status_code=status.HTTP_200_OK)
def delete_submitted_task(
    task_id: str,
    handler: BlueskyHandler = Depends(get_handler),
) -> TaskResponse:
    return TaskResponse(task_id=handler.clear_task(task_id))


def validate_task_status(v: str) -> TaskStatusEnum:
    v_upper = v.upper()
    if v_upper not in TaskStatusEnum.__members__:
        raise ValueError("Invalid status query parameter")
    return TaskStatusEnum(v_upper)


@app.get("/tasks", response_model=TasksListResponse, status_code=status.HTTP_200_OK)
def get_tasks(
    task_status: str | None = None,
    handler: BlueskyHandler = Depends(get_handler),
) -> TasksListResponse:
    """
    Retrieve tasks based on their status.
    The status of a newly created task is 'unstarted'.
    """
    tasks = []
    if task_status:
        try:
            desired_status = validate_task_status(task_status)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status query parameter",
            ) from e

        tasks = handler.get_tasks_by_status(desired_status)
    else:
        tasks = handler.tasks
    return TasksListResponse(tasks=tasks)


@app.put(
    "/worker/task",
    response_model=WorkerTask,
    responses={status.HTTP_409_CONFLICT: {"worker": "already active"}},
)
def set_active_task(
    task: WorkerTask,
    handler: BlueskyHandler = Depends(get_handler),
) -> WorkerTask:
    """Set a task to active status, the worker should begin it as soon as possible.
    This will return an error response if the worker is not idle."""
    active_task = handler.active_task
    if active_task is not None and not active_task.is_complete:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Worker already active"
        )
    handler.begin_task(task)
    return task


@app.get(
    "/tasks/{task_id}",
    response_model=TrackableTask,
)
def get_task(
    task_id: str,
    handler: BlueskyHandler = Depends(get_handler),
) -> TrackableTask:
    """Retrieve a task"""
    task = handler.get_task_by_id(task_id)
    if task is None:
        raise KeyError
    return task


@app.get("/worker/task")
def get_active_task(handler: BlueskyHandler = Depends(get_handler)) -> WorkerTask:
    active = handler.active_task
    if active is not None:
        return WorkerTask(task_id=active.task_id)
    else:
        return WorkerTask(task_id=None)


@app.get("/worker/state")
def get_state(handler: BlueskyHandler = Depends(get_handler)) -> WorkerState:
    """Get the State of the Worker"""
    return handler.worker_state


# Map of current_state: allowed new_states
_ALLOWED_TRANSITIONS: dict[WorkerState, set[WorkerState]] = {
    WorkerState.RUNNING: {
        WorkerState.PAUSED,
        WorkerState.ABORTING,
        WorkerState.STOPPING,
    },
    WorkerState.PAUSED: {
        WorkerState.RUNNING,
        WorkerState.ABORTING,
        WorkerState.STOPPING,
    },
}


@app.put(
    "/worker/state",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"detail": "Transition not allowed"},
        status.HTTP_202_ACCEPTED: {"detail": "Transition requested"},
    },
)
def set_state(
    state_change_request: StateChangeRequest,
    response: Response,
    handler: BlueskyHandler = Depends(get_handler),
) -> WorkerState:
    """
    Request that the worker is put into a particular state.
    Returns the state of the worker at the end of the call.

    - **The following transitions are allowed and return 202: Accepted**
    - If the worker is **PAUSED**, new_state may be **RUNNING** to resume.
    - If the worker is **RUNNING**, new_state may be **PAUSED** to pause:
        - If defer is False (default): pauses and rewinds to the previous checkpoint
        - If defer is True: waits until the next checkpoint to pause
        - **If the task has no checkpoints, the task will instead be Aborted**
    - If the worker is **RUNNING/PAUSED**, new_state may be **STOPPING** to stop.
        Stop marks any currently open Runs in the Task as a success and ends the task.
    - If the worker is **RUNNING/PAUSED**, new_state may be **ABORTING** to abort.
        Abort marks any currently open Runs in the Task as a Failure and ends the task.
        - If reason is set, the reason will be passed as the reason for the Run failure.
    - **All other transitions return 400: Bad Request**
    """
    current_state = handler.worker_state
    new_state = state_change_request.new_state
    if (
        current_state in _ALLOWED_TRANSITIONS
        and new_state in _ALLOWED_TRANSITIONS[current_state]
    ):
        if new_state == WorkerState.PAUSED:
            handler.pause_worker(defer=state_change_request.defer)
        elif new_state == WorkerState.RUNNING:
            handler.resume_worker()
        elif new_state in {WorkerState.ABORTING, WorkerState.STOPPING}:
            try:
                handler.cancel_active_task(
                    state_change_request.new_state is WorkerState.ABORTING,
                    state_change_request.reason,
                )
            except TransitionError:
                response.status_code = status.HTTP_400_BAD_REQUEST
    else:
        response.status_code = status.HTTP_400_BAD_REQUEST

    return handler.worker_state


def start(config: ApplicationConfig):
    import uvicorn

    app.state.config = config
    uvicorn.run(app, host=config.api.host, port=config.api.port)


@app.middleware("http")
async def add_api_version_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-API-Version"] = REST_API_VERSION
    return response
