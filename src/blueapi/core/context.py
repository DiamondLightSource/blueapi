from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Dict, Iterable, Optional

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

    def plan_module(self, module: ModuleType) -> None:
        """
        Register all functions in the module supplied as plans. Module should take the form:

        def plan_1(...):
            ...

        def _helper(...):
            ...

        def plan_2(...):
            ...

        __all__ = ["plan_1", "plan_2"]

        Args:
            module (ModuleType): Module to pass in
        """

        for obj in load_module_all(module):
            self.plan(obj)

    def plan(self, plan: PlanGenerator) -> PlanGenerator:
        """
        Register the argument as a plan in the context. Can be used as a decorator e.g.
        @ctx.plan
        def my_plan(a: int, b: str):
            ...

        Args:
            plan (PlanGenerator): Plan generator function to register

        Returns:
            PlanGenerator: The plan passed in for chaining/decorating
        """

        schema = schema_for_func(plan)
        self.plans[plan.__name__] = Plan(plan.__name__, schema)
        self.plan_functions[plan.__name__] = plan
        return plan

    def ability(self, ability: Ability, name: Optional[str] = None) -> None:
        """
        Register an ability in the context. The ability needs to be registered with a name.
        If the ability is Readable, Movable or Flyable it has a `name` attribbute which can be used.
        The attribute can be overrideen with the `name` parameter here. If the ability conforms to a
        different protocol then the parameter must be used to name it.

        Args:
            ability (Ability): The ability to register
            name (Optional[str], optional): A name for the ability. Defaults to None.

        Raises:
            KeyError: If no name is found/supplied
        """

        if name is None:
            if isinstance(ability, Readable) or isinstance(ability, Flyable):
                name = ability.name
            else:
                raise KeyError("Must supply a name for this ability")

        self.abilities[name] = ability


def load_module_all(mod: ModuleType) -> Iterable[Any]:
    """
    Load the global variables exported via the `__all__` magic variable in a module.
    Dynamic equivalent to `from my_module import *`. Raise an exception if the
    module doesn't have an explicit `__all__`

    .. code:: python

        from importlib import import_module

        mod = import_module("example.hello")
        variables = load_module_all(mod)

    :param mod: The module to extract `__all__` from
    :yield: Each successive variable in `__all__`
    """

    if "__all__" in mod.__dict__:
        names = mod.__dict__["__all__"]
        for name in names:
            yield getattr(mod, name)
    else:
        raise TypeError(f"{mod} must have an explicit __all__ variable")
