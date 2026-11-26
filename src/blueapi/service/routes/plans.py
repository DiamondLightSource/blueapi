from fastapi import APIRouter
from observability_utils.tracing import start_as_current_span

from blueapi.config import Tag
from blueapi.service import interface
from blueapi.service.model import PlanModel, PlanResponse

from .dependencies import TRACER, Runner

router = APIRouter(tags=[Tag.PLAN])


@router.get("/plans")
@start_as_current_span(TRACER)
def get_plans(runner: Runner) -> PlanResponse:
    """Retrieve information about all available plans."""
    plans = runner.run(interface.get_plans)
    return PlanResponse(plans=plans)


@router.get("/plans/{name}")
@start_as_current_span(TRACER, "name")
def get_plan_by_name(name: str, runner: Runner) -> PlanModel:
    """Retrieve information about a plan by its (unique) name."""
    return runner.run(interface.get_plan, name)
