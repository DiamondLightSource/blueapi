from types import ModuleType
from typing import Any, Iterable


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
