import re
from collections.abc import Callable, Mapping
from functools import wraps
from logging import Logger
from typing import Any, ParamSpec, TypeVar

from .base_model import BlueapiBaseModel, BlueapiModelConfig, BlueapiPlanModelConfig
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
    "report_successful_devices",
    "is_sgid_set",
    "get_owner_gid",
    "is_function_sourced_from_module",
    "deprecated",
]

Args = ParamSpec("Args")
Return = TypeVar("Return")

INSTRUMENT_SESSION_RE = re.compile(r"^[a-z]{2}(?P<proposal>\d+)-(?P<visit>\d+)$")


def report_successful_devices(
    devices: Mapping[str, Any], sim_backend: bool, logger: Logger
) -> None:
    sim_statement = " (sim mode)" if sim_backend else ""
    connected_devices = "\n".join(
        sorted([f"\t{device_name}" for device_name in devices.keys()])
    )

    logger.info(f"{len(devices)} devices connected{sim_statement}:")
    logger.info(connected_devices)


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
