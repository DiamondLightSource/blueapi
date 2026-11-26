from io import StringIO
from textwrap import dedent
from types import FunctionType
from typing import Any
from unittest.mock import Mock

import pytest

from blueapi.cli.stubgen import (
    DEV_TMPL,
    PLAN_TMPL,
    PlanSpec,
    _docstring,
    _type_string,
    generate_stubs,
    render_stub_file,
)
from blueapi.client.device_cache import DeviceRef
from blueapi.client.plan_cache import Plan
from blueapi.service.model import DeviceModel, PlanModel


def single_line():
    """Single line docstring"""


def single_line_new_line():
    """
    Single line docstring
    """


def multi_line_inline():
    """First line
    Second line"""


def multi_line_new_line():
    """
    First line
    Second line
    """


def indented_multi_line():
    """
    First line
        indented
    """


@pytest.mark.parametrize(
    "input,expected",
    [
        (single_line, "Single line docstring"),
        (single_line_new_line, "Single line docstring"),
        (multi_line_inline, "First line\nSecond line"),
        (multi_line_new_line, "First line\nSecond line"),
        (indented_multi_line, "First line\n    indented"),
    ],
)
def test_docstring_filter(input: FunctionType, expected: str):
    assert input.__doc__
    assert _docstring(input.__doc__) == expected


@pytest.mark.parametrize(
    "typ,expected",
    [
        ({"type": "string"}, "str"),
        ({"type": "number"}, "float"),
        ({"type": "integer"}, "int"),
        ({"type": "object"}, "dict[str, Any]"),
        ({"type": "boolean"}, "bool"),
        ({"type": "array", "items": {"type": "integer"}}, "list[int]"),
        ({"type": "array", "items": {"type": "object"}}, "list[dict[str, Any]]"),
        (
            {
                "type": "array",
                "items": {"anyOf": [{"type": "integer"}, {"type": "boolean"}]},
            },
            "list[int | bool]",
        ),
        ({"anyOf": [{"type": "object"}, {"type": "string"}]}, "dict[str, Any] | str"),
        ({"type": "unknown.other.Type"}, "Any"),
        # Special case the bluesky protocols to require device references
        ({"type": "bluesky.protocols.Readable"}, "DeviceRef"),
        ({}, "Any"),
    ],
    ids=lambda param: param.get("type") if isinstance(param, dict) else param,
)
def test_type_string(typ: dict, expected: str):
    assert _type_string(typ) == expected


@pytest.mark.parametrize(
    "template,model",
    [
        (DEV_TMPL, {"devices": []}),
        (PLAN_TMPL, {"plans": []}),
    ],
)
def test_render_empty(template: str, model: dict[str, Any]):
    output = StringIO()

    render_stub_file(output, template, **model)
    assert _extract_rendered(output) == ""


FOO = PlanModel(name="empty", description="Doc string for empty", schema={})

BAR = PlanModel(
    name="two_args",
    description="Doc string for two_args",
    schema={
        "properties": {
            "one": {"type": "integer"},
            "two": {"type": "string"},
        },
        "required": ["one"],
    },
)


def test_render_empty_plan_function():
    output = StringIO()
    plans = [Plan(name="empty", model=FOO, runner=Mock())]
    plan_model = [PlanSpec.from_plan(p) for p in plans]
    render_stub_file(output, PLAN_TMPL, plans=plan_model)
    rendered = _extract_rendered(output)

    assert (
        rendered
        == """\
    def empty(self,
    ) -> TaskStatus:
        \"""
        Doc string for empty
        \"""
        ...\n"""
    )


def test_render_multiple_plan_functions():
    output = StringIO()
    runner = Mock()
    plans = [Plan("empty", FOO, runner), Plan("two_args", BAR, runner)]
    plan_model = [PlanSpec.from_plan(p) for p in plans]
    render_stub_file(output, PLAN_TMPL, plans=plan_model)
    rendered = _extract_rendered(output)

    assert (
        rendered
        == """\
    def empty(self,
    ) -> TaskStatus:
        \"""
        Doc string for empty
        \"""
        ...
    def two_args(self,
            one: int,
            two: str | None = None,
    ) -> TaskStatus:
        \"""
        Doc string for two_args
        \"""
        ...\n"""
    )


def test_device_fields():
    output = StringIO()
    cache = Mock()
    devices = [
        DeviceRef("one", cache, DeviceModel(name="one", protocols=[])),
        DeviceRef("two", cache, DeviceModel(name="two", protocols=[])),
    ]
    render_stub_file(output, DEV_TMPL, devices=devices)

    assert _extract_rendered(output) == "    one: DeviceRef\n    two: DeviceRef\n"


def test_package_creation(tmp_path):

    stub_root = tmp_path / "blueapi-stubs"

    generate_stubs(stub_root, [], [])
    with open(stub_root / "pyproject.toml") as pyproj:
        assert pyproj.read().startswith(
            dedent("""
            [project]
            name = "blueapi-stubs"
            version = "0.1.0"
            """)
        )

    stub_src = stub_root / "src" / "blueapi-stubs"

    with open(stub_src / "py.typed") as typed:
        assert typed.read() == "partial\n"

    assert (stub_src / "client" / "device_cache.pyi").exists()
    assert (stub_src / "client" / "plan_cache.pyi").exists()


def _extract_rendered(src: StringIO) -> str:
    src.seek(0)
    _read_until_line(src, "### Generated")
    return _read_until_line(src, "### End")


def _read_until_line(src: StringIO, match: str) -> str:
    text = ""
    for line in src:
        if line.startswith(match):
            break
        text += line

    return text
