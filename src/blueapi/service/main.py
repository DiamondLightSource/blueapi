from contextlib import asynccontextmanager
from typing import Any, Mapping

from fastapi import Body, Depends, FastAPI, HTTPException

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
def get_plans(handler: Handler = Depends(get_handler)):
    """Retrieve information about all available plans."""
    return PlanResponse(
        plans=[PlanModel.from_plan(plan) for plan in handler.context.plans.values()]
    )


@app.get("/plan/{name}", response_model=PlanModel)
def get_plan_by_name(name: str, handler: Handler = Depends(get_handler)):
    """Retrieve information about a plan by its (unique) name."""
    try:
        return PlanModel.from_plan(handler.context.plans[name])
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.get("/devices", response_model=DeviceResponse)
def get_devices(handler: Handler = Depends(get_handler)):
    """Retrieve information about all available devices."""
    return DeviceResponse(
        devices=[
            DeviceModel.from_device(device)
            for device in handler.context.devices.values()
        ]
    )


@app.get("/device/{name}", response_model=DeviceModel)
def get_device_by_name(name: str, handler: Handler = Depends(get_handler)):
    """Retrieve information about a devices by its (unique) name."""
    try:
        return DeviceModel.from_device(handler.context.devices[name])
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.put("/task/{name}", response_model=TaskResponse)
def submit_task(
    name: str,
    task: Mapping[str, Any] = Body(..., example={"detectors": ["x"]}),
    handler: Handler = Depends(get_handler),
):
    """Submit a task onto the worker queue."""
    task_id = handler.worker.submit_task(RunPlan(name=name, params=task))
    handler.worker.begin_task(task_id)
    return TaskResponse(task_id=task_id)


@app.get("/worker/state")
async def get_state(handler: Handler = Depends(get_handler)) -> WorkerState:
    """Get the State of the Worker"""
    return handler.worker.state


def start(config: ApplicationConfig):
    import uvicorn

    app.state.config = config
    uvicorn.run(app, host=config.api.host, port=config.api.port)
