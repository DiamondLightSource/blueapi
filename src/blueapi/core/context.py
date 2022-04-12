from dataclasses import dataclass, field
from typing import Dict, Optional

from bluesky import RunEngine
from bluesky.protocols import Flyable, Readable

from .bluesky_types import Ability, Plan, PlanGenerator
from .schema import schema_for_func


@dataclass
class BlueskyContext:
    """
    Context for building a Bluesky application
    """

    run_engine: RunEngine = field(
        default_factory=lambda: RunEngine(context_managers=[])
    )
    plans: Dict[str, Plan] = field(default_factory=dict)
    abilities: Dict[str, Ability] = field(default_factory=dict)
    plan_functions: Dict[str, PlanGenerator] = field(default_factory=dict)

    def plan(self, plan: PlanGenerator) -> PlanGenerator:
        schema = schema_for_func(plan)
        self.plans[plan.__name__] = Plan(plan.__name__, schema)
        self.plan_functions[plan.__name__] = plan
        return plan

    def ability(self, ability: Ability, name: Optional[str] = None) -> None:
        if name is None:
            if isinstance(ability, Readable) or isinstance(ability, Flyable):
                name = ability.name
            else:
                raise KeyError("Must supply a name for this ability")

        self.abilities[name] = ability
