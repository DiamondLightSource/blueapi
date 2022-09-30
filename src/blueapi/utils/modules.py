from types import ModuleType
from typing import Any, Iterable


def load_module_all(mod: ModuleType) -> Iterable[Any]:
    """
    Load the global variables exported via the `__all__` magic variable in a module.
    Dynamic equivalent to `from my_module import *`. Use everything that doesn't start
    with `_` if the module doesn't have an `__all__`.

    from importlib import import_module

    mod = import_module("example.hello")
    variables = load_module_all(mod)

    Args:
        mod (ModuleType): The module to extract globals from

    Yields:
        Iterator[Iterable[Any]]: Each successive variable in globals
    """

    if "__all__" in mod.__dict__:
        names = mod.__dict__["__all__"]
        for name in names:
            yield getattr(mod, name)
    else:
        for name, value in mod.__dict__.items():
            if not name.startswith("_"):
                yield value
