from dataclasses import dataclass, field
from typing import Dict

from .bluesky_types import Plan, PlanGenerator
from .schema import schema_for_func


@dataclass
class BlueskyContext:
    """
    Context for building a Bluesky application
    """

    plans: Dict[str, Plan] = field(default_factory=dict)
    plan_functions: Dict[str, PlanGenerator] = field(default_factory=dict)

    def plan(self, plan: PlanGenerator) -> PlanGenerator:
        schema = schema_for_func(plan)
        self.plans[plan.__name__] = Plan(plan.__name__, schema)
        self.plan_functions[plan.__name__] = plan
        return plan
