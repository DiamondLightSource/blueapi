from contextlib import asynccontextmanager
from typing import Mapping

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response

from blueapi.config import ApplicationConfig
from blueapi.worker import RunPlan, WorkerState

from .handler import Handler, get_handler, setup_handler, teardown_handler
from .model import DeviceModel, DeviceResponse, PlanModel, PlanResponse, TaskResponse


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
)


@app.get("/plans", response_model=PlanResponse)
async def get_plans(response: Response, handler: Handler = Depends(get_handler)):
    """Retrieve information about all available plans."""
    add_response_headers(response)
    return PlanResponse(
        plans=[PlanModel.from_plan(plan) for plan in handler.context.plans.values()]
    )


@app.get("/plans/{name}", response_model=PlanModel)
async def get_plan_by_name(
    response: Response, name: str, handler: Handler = Depends(get_handler)
):
    """Retrieve information about a plan by its (unique) name."""
    try:
        add_response_headers(response)
        return PlanModel.from_plan(handler.context.plans[name])
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.get("/devices", response_model=DeviceResponse)
async def get_devices(response: Response, handler: Handler = Depends(get_handler)):
    """Retrieve information about all available devices."""
    add_response_headers(response)
    return DeviceResponse(
        devices=[
            DeviceModel.from_device(device)
            for device in handler.context.devices.values()
        ]
    )


@app.get("/devices/{name}", response_model=DeviceModel)
async def get_device_by_name(
    response: Response, name: str, handler: Handler = Depends(get_handler)
):
    """Retrieve information about a devices by its (unique) name."""
    try:
        add_response_headers(response)
        return DeviceModel.from_device(handler.context.devices[name])
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/tasks", response_model=TaskResponse, status_code=201)
async def submit_task(
    request: Request,
    response: Response,
    task: RunPlan = Body(
        ..., example=RunPlan(name="count", params={"detectors": ["x"]})
    ),
    handler: Handler = Depends(get_handler),
):
    """Submit a task to the worker."""
    task_id: str = handler.worker.submit_task(task)
    add_response_headers(response, {"Location": f"{request.url}/{task_id}"})
    handler.worker.begin_task(task_id)
    return TaskResponse(task_id=task_id)


@app.get("/worker/state")
async def get_state(handler: Handler = Depends(get_handler)) -> WorkerState:
    """Get the State of the Worker"""
    return handler.worker.state


def start(config: ApplicationConfig):
    import uvicorn

    app.state.config = config
    app.version = config.api.version
    uvicorn.run(app, host=config.api.host, port=config.api.port)


def add_response_headers(
    response: Response, extra_headers: Mapping[str, str] = {}
) -> None:
    response.headers.update({"X-API-Version": app.version})
    response.headers.update(extra_headers)
