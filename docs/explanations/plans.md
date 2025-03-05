# Plans

While the bluesky project uses `plan` in a general sense to refer to any `Iterable` of `Msg`'s which may be run by the `RunEngine`, blueapi distinguishes between a `plan` and a `stub`. This distinction is made to allow for a subset of `stub`'s to be exposed and run, as `stub`'s may not make sense to run alone.

Generally, a `plan` includes at least one `open_run` and `close_run` and is a complete description of an experiment. If it does not, it is a `stub`. This distinction is made in the bluesky core library between the `plan`'s and `plan_stub`'s modules.


## Allowed Argument Types

When added to the blueapi context, `PlanGenerator`'s are formalised into their schema - [a Pydantic BaseModel](https://docs.pydantic.dev/1.10/usage/models) with the expected argument types and their defaults. 

Therefore, `PlanGenerator`'s must only take as arguments [those types which are valid Pydantic fields](https://docs.pydantic.dev/dev/concepts/types) or Device types which implement `BLUESKY_PROTOCOLS` defined in dodal, which are fetched from the context at runtime.

Allowed argument types for Pydantic BaseModels include the primitives, types that extend `BaseModel` and `dict`'s, `list`'s  and other `sequence`'s of supported types. Blueapi will deserialise these types from JSON, so `dict`'s must use `str` keys.


## Stubs

Some functionality in your plans may make sense to factor out to allow re-use. These pieces of functionality may or may not make sense outside of the context of a plan. Some will, such as nudging a motor, but others may not, such as waiting to consume data from the previous position, or opening a run without an equivalent closure.

To enable blueapi to expose the stubs that it makes sense to, but not the others, blueapi will only expose a subset of `MsgGenerator`'s under the following conditions:

- `__init__.py` in directory has `__exports__`: List[str]: only those named in `__exports__`
- `__init__.py` in directory has `__all__`: List[str] but no `__exports__`: only those named in `__all__`

This allows other python packages (such as `plans`) to access every function in `__all__`, while only allowing a subset to be called from blueapi as standalone.

```python
# Rehomes all of the beamline's devices. May require to be run standalone
from .package import rehome_devices
# Awaits a standard callback from analysis. Should not be run standalone
from .package import await_callback

# Exported from the module for use by other modules
__all__ = [
    "rehome_devices",
    "await_callback",
]

# Imported by instances of blueapi and allowed to be run
__exports__ = [
    "rehome_devices",
]
```
