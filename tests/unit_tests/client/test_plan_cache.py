from textwrap import dedent
from unittest.mock import Mock

import pytest

from blueapi.client.client import PlanCache
from blueapi.client.plan_cache import Plan
from blueapi.service.model import PlanModel, TaskParametersV2, TaskRequestV2

FULL_PLAN = PlanModel(
    name="foobar",
    description="Description of plan foobar",
    schema={
        "title": "foobar",
        "description": "Model description of plan foobar",
        "properties": {
            "one": {},
            "two": {},
        },
        "required": ["one"],
    },
)


def test_plan_cache_ignores_underscores(client):
    cache = PlanCache(client, [PlanModel(name="_ignored"), PlanModel(name="used")])
    with pytest.raises(AttributeError, match="_ignored"):
        _ = cache._ignored


def test_plan_cache_repr(client):
    assert repr(client.plans) == "PlanCache(2 plans)"


def test_plan_help_text(client):
    plan = Plan("foo", PlanModel(name="foo", description="help for foo"), client)
    assert plan.help_text == "help for foo"


def test_plan_fallback_help_text(client):
    plan = Plan(
        "foo",
        PlanModel(
            name="foo",
            schema={"properties": {"one": {}, "two": {}}, "required": ["one"]},
        ),
        client,
    )
    assert plan.help_text == "Plan foo(one: Any, two: Any | None = None)"


def test_plan_multi_parameter_fallback_help_text(client):
    plan = Plan(
        "foo",
        PlanModel(
            name="foo",
            schema={
                "properties": {
                    "one": {},
                    "two": {
                        "anyOf": [{"items": {}, "type": "array"}, {"type": "boolean"}],
                    },
                    "three": {"default": 3},
                    "four": {"default": None},
                },
                "required": ["one", "two"],
            },
        ),
        client,
    )
    assert plan.help_text == dedent("""\
            Plan foo(
                one: Any,
                two: list[Any] | bool,
                three: Any = 3,
                four: Any | None = None
            )""")


def test_plan_help_text_with_ref(client):
    schema = {
        "$defs": {
            "Spec": {
                "properties": {
                    "foo": {"type": "integer"},
                    "bar": {"$ref": "#/$defs/InnerSpec"},
                },
                "required": ["foo", "bar"],
            },
            "InnerSpec": {
                "properties": {
                    "x": {"type": "number"},
                    "y": {"default": 10, "type": "number"},
                },
                "required": ["x"],
            },
        },
        "properties": {
            "spec": {"$ref": "#/$defs/Spec"},
            "meta": {"type": "string", "default": "abc"},
        },
        "required": ["spec"],
    }

    plan = Plan("ref_plan", PlanModel(name="ref_plan", schema=schema), client)
    expected = "Plan ref_plan(spec: Spec, meta: str = 'abc')"

    assert plan.help_text == expected


def test_plan_properties(client):
    plan = Plan(
        "foo",
        PlanModel(
            name="foo",
            schema={"properties": {"one": {}, "two": {}}, "required": ["one"]},
        ),
        client,
    )
    assert plan.properties == {"one": {}, "two": {}}
    assert plan.required == ["one"]


def test_plan_empty_fallback_help_text(client):
    plan = Plan(
        "foo", PlanModel(name="foo", schema={"properties": {}, "required": []}), client
    )
    assert plan.help_text == "Plan foo()"


p = pytest.param


@pytest.mark.parametrize(
    "plan_args",
    [
        pytest.param(
            TaskParametersV2(args=(1,), kwargs={}),
            id="required_as_positional",
        ),
        pytest.param(
            TaskParametersV2(args=(), kwargs={"one": 7}),
            id="required_as_keyword",
        ),
        pytest.param(
            TaskParametersV2(args=(1,), kwargs={"two": 23}),
            id="all_as_mixed_args_kwargs",
        ),
        p(
            TaskParametersV2(args=(1, 2), kwargs={}),
            id="all_as_positional",
        ),
        p(
            TaskParametersV2(args=(), kwargs={"one": 21, "two": 42}),
            id="all_as_keyword",
        ),
    ],
)
def test_plan_param_mapping(plan_args):
    client = Mock()
    client.instrument_session = "cm12345-1"
    plan = Plan("foobar", FULL_PLAN, client)

    plan(*plan_args.args, **plan_args.kwargs)
    client.run_task.assert_called_once_with(
        TaskRequestV2(name="foobar", instrument_session="cm12345-1", params=plan_args)
    )


@pytest.mark.parametrize(
    "args,kwargs,msg",
    [
        p((), {}, r"Missing argument\(s\) for \{'one'\}", id="missing_required"),
        p((1,), {"one": 7}, "multiple values for one", id="duplicate_required"),
        p((1, 2), {"two": 23}, "multiple values for two", id="duplicate_optional"),
        p((1, 2, 3), {}, "too many arguments", id="too_many_args"),
        p(
            (),
            {"unknown_key": 42},
            r"got unexpected arguments: \{'unknown_key'\}",
            id="unknown_arg",
        ),
    ],
)
def test_plan_invalid_param_mapping(args, kwargs, msg):
    client = Mock()
    client.instrument_session = "cm12345-1"
    plan = Plan("foobar", FULL_PLAN, client)

    with pytest.raises(TypeError, match=msg):
        plan(*args, **kwargs)
    client.run_task.assert_not_called()
