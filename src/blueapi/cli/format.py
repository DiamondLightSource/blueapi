import builtins
import enum
import json
import sys
import textwrap
from functools import partial
from pprint import pprint
from textwrap import dedent, indent
from typing import Any, TextIO

from pydantic import BaseModel

from blueapi.core.bluesky_types import DataEvent
from blueapi.service.model import (
    DeviceModel,
    DeviceResponse,
    PlanModel,
    PlanResponse,
    PythonEnvironmentResponse,
    SourceInfo,
)
from blueapi.worker.event import ProgressEvent, WorkerEvent

FALLBACK = pprint
NL = "\n"

Stream = TextIO | None


def fmt_dict(t: dict[str, Any] | Any, ind: int = 1) -> str:
    """Format a (possibly nested) dict into a human readable tree"""
    if not isinstance(t, dict):
        return f" {t}"
    pre = " " * (ind * 4)
    return NL + NL.join(f"{pre}{k}:{fmt_dict(v, ind + 1)}" for k, v in t.items() if v)


class OutputFormat(str, enum.Enum):
    JSON = "json"
    FULL = "full"
    COMPACT = "compact"

    def display(self, obj: Any, out: Stream = None):
        out = out or sys.stdout
        match self:
            case OutputFormat.FULL:
                display_full(obj, out)
            case OutputFormat.COMPACT:
                display_compact(obj, out)
            case OutputFormat.JSON:
                display_json(obj, out)


def display_full(obj: Any, stream: Stream):
    print = partial(builtins.print, file=stream)
    match obj:
        case PlanResponse(plans=plans):
            for plan in plans:
                display_full(plan, stream)
        case PlanModel(name=name, description=desc, parameter_schema=schema):
            print(name)
            if desc:
                print(indent(dedent(desc).strip(), "    "))
            if schema:
                print("    Schema")
                print(indent(json.dumps(schema, indent=2), "        "))
        case DeviceResponse(devices=devices):
            for dev in devices:
                display_full(dev, stream)
        case DeviceModel(name=name, protocols=protocols):
            print(name)
            for proto in protocols:
                print(f"    {proto}")
        case DataEvent(name=name, doc=doc):
            print(f"{name.title()}:{fmt_dict(doc)}")
        case WorkerEvent(state=st, task_status=task):
            print(
                f"WorkerEvent: {st.name}{fmt_dict(task.model_dump() if task else {})}"
            )
        case ProgressEvent():
            print(f"Progress:{fmt_dict(obj.model_dump())}")
        case PythonEnvironmentResponse(
            installed_packages=installed_packages, scratch_enabled=enabled
        ):
            print(f"Scratch Status: {'enabled' if enabled else 'disabled'}")
            if not installed_packages:
                print("No scratch packages found")
            else:
                print("Installed Packages:")
                for package in installed_packages:
                    print(
                        f"- {package.name}\n"
                        + f"Version: {package.version}\n"
                        + f"Location: {package.location}\n"
                        + f"Source: {package.source}\n"
                        + f"Dirty: {package.is_dirty}"
                    )
        case BaseModel():
            print(obj.__class__.__name__, end="")
            print(fmt_dict(obj.model_dump()))
        case list():
            for item in obj:
                display_full(item, stream)
        case other:
            FALLBACK(other, stream=stream)


def display_json(obj: Any, stream: Stream):
    print = partial(builtins.print, file=stream)
    match obj:
        case PlanResponse(plans=plans):
            display_json(plans, stream)
        case DeviceResponse(devices=devices):
            display_json(devices, stream)
        case BaseModel():
            print(json.dumps(obj.model_dump()))
        case list():
            print(json.dumps([it.model_dump() for it in obj], indent=2))
        case _:
            print(json.dumps(obj))


def display_compact(obj: Any, stream: Stream):
    print = partial(builtins.print, file=stream)
    match obj:
        case PlanResponse(plans=plans):
            for plan in plans:
                display_compact(plan, stream)
        case PlanModel(name=name, description=desc, parameter_schema=schema):
            print(name)
            if desc:
                print(indent(dedent(desc.split("\n\n")[0].strip("\n")), "    "))
            if schema:
                print("    Args")
                for arg, spec in schema.get("properties", {}).items():
                    req = arg in schema.get("required", {})
                    print(f"      {arg}={_describe_type(spec, req)}")
        case DeviceResponse(devices=devices):
            for dev in devices:
                display_compact(dev, stream)
        case DeviceModel(name=name, protocols=protocols):
            print(name)
            print(
                indent(
                    textwrap.fill(
                        ", ".join(str(proto) for proto in protocols),
                        80,
                    ),
                    "    ",
                )
            )
        case DataEvent(name=name):
            print(f"Data Event: {name}")
        case WorkerEvent(state=state):
            print(f"Worker Event: {state.name}")
        case ProgressEvent(statuses=stats):
            prog = (
                max(100 * (s.percentage or 0) for s in stats.values())
                if stats
                else "???"
            )
            print(f"Progress: {prog}%")
        case PythonEnvironmentResponse(
            installed_packages=installed_packages, scratch_enabled=enabled
        ):
            print(f"Scratch Status: {'enabled' if enabled else 'disabled'}")
            if not installed_packages:
                print("No scratch packages found")
            else:
                for package in installed_packages:
                    extra = ""
                    if package.is_dirty:
                        extra += " (Dirty)"
                    if package.source == SourceInfo.SCRATCH:
                        extra += " (Scratch)"
                    print(f"- {package.name} @ ({package.version}){extra}")

        case list():
            for item in obj:
                display_compact(item, stream)
        case other:
            FALLBACK(other, stream=stream)


def _describe_type(spec: dict[Any, Any], required: bool = False):
    disp = ""
    match spec.get("type"):
        case None:
            if all_of := spec.get("allOf"):
                items = (_describe_type(f, False) for f in all_of)
                disp += f"{' & '.join(items)}"
            elif any_of := spec.get("anyOf"):
                items = (_describe_type(f, False) for f in any_of)

                # Special case: Where the type is <something> | null,
                # we should just print <something>
                items = (item for item in items if item != "null" or len(any_of) != 2)
                disp += f"{' | '.join(items)}"
            else:
                disp += "Any"
        case "array":
            element = spec.get("items", {}).get("type", "Any")
            disp += f"[{element}]"
        case other:
            disp += other
    if required:
        disp += " (Required)"
    return disp
