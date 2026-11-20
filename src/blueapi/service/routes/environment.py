from fastapi import APIRouter, BackgroundTasks
from observability_utils.tracing import start_as_current_span

from blueapi.config import Tag
from blueapi.service import interface
from blueapi.service.model import (
    EnvironmentResponse,
    PythonEnvironmentResponse,
    SourceInfo,
)

from .dependencies import TRACER, Runner

router = APIRouter(tags=[Tag.ENV])


@router.get("/environment")
@start_as_current_span(TRACER)
def get_environment(runner: Runner) -> EnvironmentResponse:
    """Get the current state of the environment, i.e. initialization state."""
    return runner.state


@router.delete("/environment")
async def delete_environment(
    background_tasks: BackgroundTasks,
    runner: Runner,
) -> EnvironmentResponse:
    """Delete the current environment, causing internal components to be reloaded."""
    environment_id = runner.state.environment_id
    if runner.state.initialized or runner.state.error_message is not None:
        background_tasks.add_task(runner.reload)
    return EnvironmentResponse(environment_id=environment_id, initialized=False)


@router.get("/python_environment")
@start_as_current_span(TRACER)
def get_python_environment(
    runner: Runner,
    name: str | None = None,
    source: SourceInfo | None = None,
) -> PythonEnvironmentResponse:
    """
    Retrieve the Python environment details.
    This endpoint fetches information about the Python environment,
    such as the installed packages and scratch packages.
    """
    return runner.run(interface.get_python_env, name, source)
