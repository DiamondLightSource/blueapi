from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from .base_model import BlueapiBaseModel, BlueapiModelConfig, BlueapiPlanModelConfig
from .connect_devices import connect_devices, report_successful_devices
from .file_permissions import get_owner_gid, is_sgid_set
from .invalid_config_error import InvalidConfigError
from .modules import is_function_sourced_from_module, load_module_all
from .numtracker import NumtrackerClient
from .serialization import serialize
from .thread_exception import handle_all_exceptions

__all__ = [
    "handle_all_exceptions",
    "load_module_all",
    "serialize",
    "BlueapiBaseModel",
    "BlueapiModelConfig",
    "BlueapiPlanModelConfig",
    "InvalidConfigError",
    "NumtrackerClient",
    "connect_devices",
    "report_successful_devices",
    "is_sgid_set",
    "get_owner_gid",
    "is_function_sourced_from_module",
    "deprecated",
]

Args = ParamSpec("Args")
Return = TypeVar("Return")


def deprecated(alternative):
    from warnings import warn

    def deprecated(func: Callable[Args, Return]) -> Callable[Args, Return]:
        called = False

        @wraps(func)
        def wrapped(*args, **kwargs):
            nonlocal called
            if not called:
                warn(
                    f"Function {func.__name__} is deprecated - use {alternative}",
                    DeprecationWarning,
                    stacklevel=2,
                )
                called = True
            return func(*args, **kwargs)

        return wrapped

    return deprecated
