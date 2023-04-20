from fastapi import APIRouter
from blueapi import context, worker

router = APIRouter()


@router.get("/plans")
async def get_plans():
    context.plans
    ...


@router.get("/plan/{name}")
async def get_plan_by_name(name: str):
    try:
        context.plans[name]
    except IndexError:
        raise Exception()  # really, return a 404.


@router.get("/devices")
async def get_devices():
    context.devices


@router.get("/device/{name}")
async def get_device_by_name(name: str):
    try:
        context.plans[name]
    except IndexError:
        raise Exception()  # really, return a 404.


@router.put("task/{name}")
async def execute_task(name: str):
    ##basically in here, do the same thing the service once did...
    # worker.submit_task(name, task)
    pass
