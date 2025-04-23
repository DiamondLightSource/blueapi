import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

import jwt
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2AuthorizationCodeBearer
from observability_utils.tracing import (
    add_span_attributes,
    get_tracer,
    start_as_current_span,
)
from opentelemetry.context import attach
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.propagate import get_global_textmap
from opentelemetry.trace import get_tracer_provider
from pydantic import ValidationError
from pydantic.json_schema import SkipJsonSchema
from starlette.responses import JSONResponse
from super_state_machine.errors import TransitionError

from blueapi.config import ApplicationConfig, OIDCConfig
from blueapi.service import interface
from blueapi.worker import Task, TrackableTask, WorkerState
from blueapi.worker.event import TaskStatusEnum

from .model import (
    DeviceModel,
    DeviceResponse,
    EnvironmentResponse,
    Health,
    HealthProbeResponse,
    PlanModel,
    PlanResponse,
    PythonEnvironmentResponse,
    SourceInfo,
    StateChangeRequest,
    TaskResponse,
    TasksListResponse,
    WorkerTask,
)
from .runner import WorkerDispatcher

#: API version to publish in OpenAPI schema
REST_API_VERSION = "0.0.10"

RUNNER: WorkerDispatcher | None = None

LOGGER = logging.getLogger(__name__)
CONTEXT_HEADER = "traceparent"


def _runner() -> WorkerDispatcher:
    """Intended to be used only with FastAPI Depends"""
    if RUNNER is None:
        raise ValueError()
    return RUNNER


def setup_runner(
    config: ApplicationConfig | None = None,
    runner: WorkerDispatcher | None = None,
):
    global RUNNER
    runner = runner or WorkerDispatcher(config)
    runner.start()

    RUNNER = runner


def teardown_runner():
    global RUNNER
    if RUNNER is None:
        return
    RUNNER.stop()
    RUNNER = None


def lifespan(config: ApplicationConfig):
    @asynccontextmanager
    async def inner(app: FastAPI):
        setup_runner(config)
        yield
        teardown_runner()

    return inner


secure_router = APIRouter()
open_router = APIRouter()


def get_app(config: ApplicationConfig):
    app = FastAPI(
        docs_url="/docs",
        title="BlueAPI Control",
        lifespan=lifespan(config),
        version=REST_API_VERSION,
    )
    dependencies = []
    if config.oidc:
        dependencies.append(Depends(verify_access_token(config.oidc)))
    app.include_router(open_router)
    app.include_router(secure_router, dependencies=dependencies)
    app.add_exception_handler(KeyError, on_key_error_404)
    app.add_exception_handler(jwt.PyJWTError, on_token_error_401)
    app.middleware("http")(add_api_version_header)
    app.middleware("http")(inject_propagated_observability_context)
    app.middleware("http")(log_request_details)
    if config.api.cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.api.cors.origins,
            allow_credentials=config.api.cors.allow_credentials,
            allow_methods=config.api.cors.allow_methods,
            allow_headers=config.api.cors.allow_headers,
        )
    return app


def verify_access_token(config: OIDCConfig):
    jwkclient = jwt.PyJWKClient(config.jwks_uri)
    oauth_scheme = OAuth2AuthorizationCodeBearer(
        authorizationUrl=config.authorization_endpoint,
        tokenUrl=config.token_endpoint,
        refreshUrl=config.token_endpoint,
    )

    def inner(access_token: str = Depends(oauth_scheme)):
        signing_key = jwkclient.get_signing_key_from_jwt(access_token)
        jwt.decode(
            access_token,
            signing_key.key,
            algorithms=config.id_token_signing_alg_values_supported,
            verify=True,
            audience=config.client_audience,
            issuer=config.issuer,
        )

    return inner


TRACER = get_tracer("interface")


async def on_key_error_404(_: Request, __: Exception):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Item not found"},
    )


async def on_token_error_401(_: Request, __: Exception):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Not authenticated"},
        headers={"WWW-Authenticate": "Bearer"},
    )


@secure_router.get("/environment")
@start_as_current_span(TRACER, "runner")
def get_environment(
    runner: Annotated[WorkerDispatcher, Depends(_runner)],
) -> EnvironmentResponse:
    """Get the current state of the environment, i.e. initialization state."""
    return runner.state


@secure_router.delete("/environment")
async def delete_environment(
    background_tasks: BackgroundTasks,
    runner: Annotated[WorkerDispatcher, Depends(_runner)],
) -> EnvironmentResponse:
    """Delete the current environment, causing internal components to be reloaded."""
    environment_id = runner.state.environment_id
    if runner.state.initialized or runner.state.error_message is not None:
        background_tasks.add_task(runner.reload)
    return EnvironmentResponse(environment_id=environment_id, initialized=False)


@open_router.get(
    "/config/oidc",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "No Authentication configured"}
    },
)
@start_as_current_span(TRACER)
def get_oidc_config(
    runner: Annotated[WorkerDispatcher, Depends(_runner)],
) -> OIDCConfig:
    """Retrieve the OpenID Connect (OIDC) configuration for the server."""
    config = runner.run(interface.get_oidc_config)
    if config is None:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)
    return config


@secure_router.get("/plans")
@start_as_current_span(TRACER)
def get_plans(runner: Annotated[WorkerDispatcher, Depends(_runner)]) -> PlanResponse:
    """Retrieve information about all available plans."""
    plans = runner.run(interface.get_plans)
    return PlanResponse(plans=plans)


@secure_router.get(
    "/plans/{name}",
)
@start_as_current_span(TRACER, "name")
def get_plan_by_name(
    name: str, runner: Annotated[WorkerDispatcher, Depends(_runner)]
) -> PlanModel:
    """Retrieve information about a plan by its (unique) name."""
    return runner.run(interface.get_plan, name)


@secure_router.get("/devices")
@start_as_current_span(TRACER)
def get_devices(
    runner: Annotated[WorkerDispatcher, Depends(_runner)],
) -> DeviceResponse:
    """Retrieve information about all available devices."""
    devices = runner.run(interface.get_devices)
    return DeviceResponse(devices=devices)


@secure_router.get(
    "/devices/{name}",
)
@start_as_current_span(TRACER, "name")
def get_device_by_name(
    name: str, runner: Annotated[WorkerDispatcher, Depends(_runner)]
) -> DeviceModel:
    """Retrieve information about a devices by its (unique) name."""
    return runner.run(interface.get_device, name)


example_task = Task(name="count", params={"detectors": ["x"]})


@secure_router.post(
    "/tasks",
    status_code=status.HTTP_201_CREATED,
)
@start_as_current_span(TRACER, "request", "task.name", "task.params")
def submit_task(
    request: Request,
    response: Response,
    task: Annotated[Task, Body(..., example=example_task)],
    runner: Annotated[WorkerDispatcher, Depends(_runner)],
) -> TaskResponse:
    """Submit a task to the worker."""
    try:
        task_id: str = runner.run(interface.submit_task, task)
        response.headers["Location"] = f"{request.url}/{task_id}"
        return TaskResponse(task_id=task_id)
    except ValidationError as e:
        # Add body/params context to location and ensure that all required
        # fields defined in the generated schema are present
        errors = [
            {
                "loc": ["body", "params", *err.get("loc", [])],
                "msg": err.get("msg", None),
                "type": err.get("type", None),
                # Input is not listed as required but is useful to have if available
                "input": err.get("input", None),
            }
            for err in e.errors()
        ]

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors,
        ) from e


@secure_router.delete("/tasks/{task_id}", status_code=status.HTTP_200_OK)
@start_as_current_span(TRACER, "task_id")
def delete_submitted_task(
    task_id: str,
    runner: Annotated[WorkerDispatcher, Depends(_runner)],
) -> TaskResponse:
    return TaskResponse(task_id=runner.run(interface.clear_task, task_id))


@start_as_current_span(TRACER, "v")
def validate_task_status(v: str) -> TaskStatusEnum:
    v_upper = v.upper()
    if v_upper not in TaskStatusEnum.__members__:
        raise ValueError("Invalid status query parameter")
    return TaskStatusEnum(v_upper)


@secure_router.get("/tasks", status_code=status.HTTP_200_OK)
@start_as_current_span(TRACER)
def get_tasks(
    runner: Annotated[WorkerDispatcher, Depends(_runner)],
    task_status: str | SkipJsonSchema[None] = None,
) -> TasksListResponse:
    """
    Retrieve tasks based on their status.
    The status of a newly created task is 'unstarted'.
    """
    tasks = []
    if task_status:
        add_span_attributes({"status": task_status})
        try:
            desired_status = validate_task_status(task_status)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status query parameter",
            ) from e

        tasks = runner.run(interface.get_tasks_by_status, desired_status)
    else:
        tasks = runner.run(interface.get_tasks)
    return TasksListResponse(tasks=tasks)


@secure_router.put(
    "/worker/task",
    responses={status.HTTP_409_CONFLICT: {}},
)
@start_as_current_span(TRACER, "task.task_id")
def set_active_task(
    request: Request,
    task: WorkerTask,
    runner: Annotated[WorkerDispatcher, Depends(_runner)],
) -> WorkerTask:
    """Set a task to active status, the worker should begin it as soon as possible.
    This will return an error response if the worker is not idle."""
    active_task = runner.run(interface.get_active_task)
    if active_task is not None and not active_task.is_complete:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Worker already active"
        )
    runner.run(
        interface.begin_task,
        task=task,
        pass_through_headers={
            key: value
            for key, value in request.headers.items()
            if key in {"Authorization"}
        },
    )
    return task


@secure_router.get(
    "/tasks/{task_id}",
)
@start_as_current_span(TRACER, "task_id")
def get_task(
    task_id: str,
    runner: Annotated[WorkerDispatcher, Depends(_runner)],
) -> TrackableTask:
    """Retrieve a task"""
    task = runner.run(interface.get_task_by_id, task_id)
    if task is None:
        raise KeyError
    return task


@secure_router.get("/worker/task")
@start_as_current_span(TRACER)
def get_active_task(
    runner: Annotated[WorkerDispatcher, Depends(_runner)],
) -> WorkerTask:
    active = runner.run(interface.get_active_task)
    task_id = active.task_id if active is not None else None
    return WorkerTask(task_id=task_id)


@secure_router.get("/worker/state")
@start_as_current_span(TRACER)
def get_state(runner: Annotated[WorkerDispatcher, Depends(_runner)]) -> WorkerState:
    """Get the State of the Worker"""
    return runner.run(interface.get_worker_state)


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


@secure_router.put(
    "/worker/state",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_202_ACCEPTED: {},
    },
)
@start_as_current_span(TRACER, "state_change_request.new_state")
def set_state(
    state_change_request: StateChangeRequest,
    response: Response,
    runner: Annotated[WorkerDispatcher, Depends(_runner)],
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
    current_state = runner.run(interface.get_worker_state)
    new_state = state_change_request.new_state
    add_span_attributes({"current_state": current_state})
    if (
        current_state in _ALLOWED_TRANSITIONS
        and new_state in _ALLOWED_TRANSITIONS[current_state]
    ):
        if new_state == WorkerState.PAUSED:
            runner.run(interface.pause_worker, state_change_request.defer)
        elif new_state == WorkerState.RUNNING:
            runner.run(interface.resume_worker)
        elif new_state in {WorkerState.ABORTING, WorkerState.STOPPING}:
            try:
                runner.run(
                    interface.cancel_active_task,
                    state_change_request.new_state is WorkerState.ABORTING,
                    state_change_request.reason,
                )
            except TransitionError:
                response.status_code = status.HTTP_400_BAD_REQUEST
    else:
        response.status_code = status.HTTP_400_BAD_REQUEST

    return runner.run(interface.get_worker_state)


@secure_router.get("/python_environment")
@start_as_current_span(TRACER)
def get_python_environment(
    runner: Annotated[WorkerDispatcher, Depends(_runner)],
    name: str | None = None,
    source: SourceInfo | None = None,
) -> PythonEnvironmentResponse:
    """
    Retrieve the Python environment details.
    This endpoint fetches information about the Python environment,
    such as the installed packages and scratch packages.
    """
    return runner.run(interface.get_python_env, name, source)


@open_router.get(
    "/healthz",
    status_code=status.HTTP_200_OK,
)
def health_probe() -> HealthProbeResponse:
    """If able to serve this, server is live and ready for requests."""
    return HealthProbeResponse(status=Health.OK)


@start_as_current_span(TRACER, "config")
def start(config: ApplicationConfig):
    import uvicorn
    from uvicorn.config import LOGGING_CONFIG

    LOGGING_CONFIG["formatters"]["default"]["fmt"] = (
        "%(asctime)s %(levelprefix)s %(message)s"
    )
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = (
        "%(asctime)s %(levelprefix)s %(client_addr)s"
        + " - '%(request_line)s' %(status_code)s"
    )
    app = get_app(config)

    FastAPIInstrumentor().instrument_app(
        app,
        tracer_provider=get_tracer_provider(),
        http_capture_headers_server_request=[",*"],
        http_capture_headers_server_response=[",*"],
    )
    app.state.config = config

    uvicorn.run(app, host=config.api.host, port=config.api.port)


async def add_api_version_header(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
):
    response = await call_next(request)
    response.headers["X-API-Version"] = REST_API_VERSION
    return response


async def log_request_details(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    LOGGER.info(
        f"method: {request.method} url: {request.url} body: {await request.body()}",
    )
    response = await call_next(request)
    return response


async def inject_propagated_observability_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Middleware to extract any propagated observability context from the
    HTTP headers and attach it to the local one.
    """
    if CONTEXT_HEADER in request.headers:
        ctx = get_global_textmap().extract(
            {CONTEXT_HEADER: request.headers[CONTEXT_HEADER]}
        )
        attach(ctx)
    response = await call_next(request)
    return response
