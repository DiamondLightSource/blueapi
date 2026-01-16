import logging
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Self

from jinja2 import Environment, PackageLoader

from blueapi.client.cache import DeviceRef, Plan
from blueapi.core import context
from blueapi.core.bluesky_types import BLUESKY_PROTOCOLS

log = logging.getLogger(__name__)


@dataclass
class ArgSpec:
    name: str
    type: str
    optional: bool


@dataclass
class PlanSpec:
    name: str
    docs: str
    args: list[ArgSpec]

    @classmethod
    def from_plan(cls, plan: Plan) -> Self:
        req = set(plan.required)
        args = [
            ArgSpec(arg, _map_type(spec), arg not in req)
            for arg, spec in plan.model.parameter_schema.get("properties", {}).items()
        ]
        return cls(plan.name, plan.help_text, args)


BLUESKY_PROTOCOL_NAMES = {context.qualified_name(proto) for proto in BLUESKY_PROTOCOLS}


def _map_type(spec) -> str:
    """Best effort attempt at making useful type hints for plans"""
    match spec.get("type"):
        case "array":
            return f"list[{_map_type(spec.get('items'))}]"
        case "integer":
            return "int"
        case "number":
            return "float"
        case proto if proto in BLUESKY_PROTOCOL_NAMES:
            return "DeviceRef"
        case "object":
            return "dict[str, Any]"
        case "string":
            return "str"
        case "boolean":
            return "bool"
        case None if opts := spec.get("anyOf"):
            return "|".join(_map_type(opt) for opt in opts)
        case _:
            return "Any"


def generate_stubs(target: Path, plans: list[Plan], devices: list[DeviceRef]):
    log.info("Generating stubs for %d plans and %d devices", len(plans), len(devices))
    target.mkdir(parents=True, exist_ok=True)
    client_dir = target / "src" / "blueapi-stubs" / "client"
    client_dir.mkdir(parents=True, exist_ok=True)
    stub_file = client_dir / "cache.pyi"
    project_file = target / "pyproject.toml"
    py_typed = target / "src" / "blueapi-stubs" / "py.typed"

    with open(project_file, "w") as out:
        out.write(
            dedent("""
                [project]
                name = "blueapi-stubs"
                version = "0.1.0"
                description = "Generated client stubs for a running server"
                readme = "README.md"
                requires-python = ">=3.11"

                dependencies = [
                    "blueapi"
                ]
                """)
        )

    with open(py_typed, "w") as out:
        out.write("partial\n")

    render_stub_file(stub_file, plans, devices)


def render_stub_file(
    stub_file: Path, plan_models: list[Plan], devices: list[DeviceRef]
):
    plans = [PlanSpec.from_plan(p) for p in plan_models]

    env = Environment(loader=PackageLoader("blueapi", package_path="stubs/templates"))
    tmpl = env.get_template("cache_template.pyi")
    with open(stub_file, "w") as out:
        out.write(tmpl.render(plans=plans, devices=devices))
