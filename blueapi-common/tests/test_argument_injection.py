from typing import Annotated

import pytest
from blueapi_common import Inject, Injected, source_args


def single_inject(x: Injected[int]): ...


def double_inject(x: Injected[int], fizz: Injected[str]): ...


def varargs(*bar: Injected[int]): ...


def pos_only(x: Injected[int], /): ...


def pos_only_named(x: Annotated[int, Inject("bar")], /): ...


def keyword_default_arg(x: int = 17): ...


def keyword_injected_arg(x: Injected[int] = 43): ...


def keyword_only_arg(*, x: Injected[int]): ...


context = {"x": 42, "bar": 73, "fizz": "buzz"}


@pytest.mark.parametrize(
    "function,args,kwargs",
    [
        (single_inject, (42,), {}),
        (double_inject, (42, "buzz"), {}),
        (varargs, (73,), {}),
        (pos_only, (42,), {}),
        (pos_only_named, (73,), {}),
        (keyword_default_arg, (17,), {}),
        (keyword_injected_arg, (43,), {}),
        (keyword_only_arg, (), {"x": 42}),
    ],
)
def test_arg_sourcing(function, args, kwargs):
    a, kw = source_args(function, (), {}, context.get)

    assert a == args
    assert kw == kwargs


@pytest.mark.parametrize(
    "function, args, kwargs, exp_args, exp_kwargs",
    [
        (single_inject, (91,), {}, (91,), {}),
        (double_inject, (91, "foo"), {}, (91, "foo"), {}),
        (double_inject, (91,), {"fizz": "foo"}, (91, "foo"), {}),
    ],
)
def test_arg_overrides(function, args, kwargs, exp_args, exp_kwargs):
    a, kw = source_args(function, args, kwargs, context.get)

    assert a == exp_args
    assert kw == exp_kwargs
