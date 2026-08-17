from typing import Annotated
from blueapi_common import Inject, source_args, Injected

def single_inject(x: Injected[int]): ...

def varargs(*args: int): ...

def pos_only(x: Injected[int], /): ...

def pos_only_named(x: Annotated[int, Inject("bar")], /): ...


context = {"x": 42, "bar": 73}

def test_single_inject():
    args, kwargs = source_args(single_inject, context.get)

    assert args == (42,)
    assert kwargs == {}
