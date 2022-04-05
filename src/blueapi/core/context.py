from dataclasses import dataclass, field
from typing import Dict, Optional

from bluesky.protocols import Flyable, Readable

from .bluesky_types import Ability, Plan, PlanGenerator
from .schema import schema_for_func

AbilityRegistry = Dict[str, Ability]


@dataclass
class BlueskyContext:
    """
    Context for building a Bluesky application
    """

    plans: Dict[str, Plan] = field(default_factory=dict)
    abilities: AbilityRegistry = field(default_factory=dict)
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

    def inject_abilities(self, plan: PlanGenerator) -> PlanGenerator:
        return lambda *args, **kwargs: plan(self.abilities, *args, **kwargs)
