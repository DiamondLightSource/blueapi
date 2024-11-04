# Writing Bluesky plans for Blueapi


For an introduction to bluesky plans and general forms/advice, `see the bluesky documentation <https://nsls-ii.github.io/bluesky/plans.html>`__. Blueapi has some additional requirements, which are explained below.

## Plans

While the bluesky project uses `plan` in a general sense to refer to any `Iterable` of `Msg`\ s which may be run by the `RunEngine`, blueapi distinguishes between a `plan` and a `stub`. This distinction is made to allow for a subset of `stub`\ s to be exposed and run, as `stub`\ s may not make sense to run alone.

Generally, a `plan` includes at least one `open_run` and `close_run` and is a complete description of an experiment. If it does not, it is a `stub`. This distinction is made in the bluesky core library between the `plan`\ s and `plan_stub`\ s modules.

## Type Annotations

To be imported into the blueapi context, `plan`\ s and `stub`\ s must be the in the form of a `PlanGenerator`: any function that return a `MsgGenerator` (a python `Generator` that yields `Msg`\ s). `PlanGenerator` and `MsgGenerator` types are available to import from `dodal`.

``` 
   def foo() -> MsgGenerator:
       # The minimum PlanGenerator acceptable to blueapi
       yield from {}
```

> **_NOTE:_** `PlanGenerator` arguments must be annotated to enable blueapi to generate their schema

**Input annotations should be as broad as possible**, the least specific implementation that is sufficient to accomplish the requirements of the plan.

For example, if a plan is written to drive a specific implementation of Movable, but never calls any methods on the device and only yields bluesky `'set'` Msgs, it can be generalised to instead use the base protocol `Movable`.

```
   def move_to_each_position(axis: Movable) -> MsgGenerator:
       # Originally written for SpecificImplementationMovable
       for _ in range(i):
           yield from abs_set(axis, location)
```

## Allowed Argument Types

When added to the blueapi context, `PlanGenerator`\ s are formalised into their schema- `a Pydantic BaseModel <https://docs.pydantic.dev/1.10/usage/models/>`__ with the expected argument types and their defaults. 

Therefore, `PlanGenerator`\ s must only take as arguments `those types which are valid Pydantic fields <https://docs.pydantic.dev/dev/concepts/types/>`__ or Device types which implement `BLUESKY_PROTOCOLS` defined in dodal, which are fetched from the context at runtime.

    Allowed argument types for Pydantic BaseModels include the primitives, types that extend `BaseModel` and `dict`\ s, `list`\ s  and other `sequence`\ s of supported types. Blueapi will deserialise these types from JSON, so `dict`\ s should use `str` keys.

## Injecting defaults

Often when writing a plan, it is known which device the plan will mostly or always be run with, but at the time of writing the plan the device object has not been instantiated: dodal defines device factory functions, but these cannot be injected as default arguments to plans.

Dodal defines an `inject` function which bypasses the type checking of the constructed schemas, defering to the blueapi contexting fetching of the device when the plan is imported. This allows defaulting devices, so long as there is a device of that name in the context which conforms to the type annotation.

``` 
   def touch_synchrotron(sync: Synchrotron = inject("synchrotron")) -> MsgGenerator:
       # There is only one Synchrotron device, so we know which one it will always be.
       # If there is no device named "synchrotron" in the blueapi context, it will except.
       sync.specific_function()
       yield from {}
```

### Metadata

The bluesky event model allows for rich structured metadata to be attached to a scan. To enable this to be used consistently, blueapi encourages a standard form.

> **_NOTE:_** Plans **should** include `metadata` as their final argument, if they do it **must** have the type Optional[Mapping[str, Any]], `and a default of None <https://stackoverflow.com/questions/26320899/why-is-the-empty-dictionary-a-dangerous-default-value-in-python>`__\, with the plan defaulting to an empty dict if passed `None`. If the plan calls to a stub/plan which takes metadata, the plan **must** pass down its metadata, which may be a differently named argument.

```
   def pass_metadata(x: Movable, metadata: Optional[Mapping[str, Any]] = None) -> MsgGenerator:
       yield from bp.count{[x], md=metadata or {}}
```

## Docstrings

Blueapi plan schemas include includes the docstrings of imported Plans. **These should therefore explain as much about the scan as cannot be ascertained from its arguments and name**. This may include units of arguments (e.g. seconds or microseconds), its purpose in the function, the purpose of the plan etc.

``` 
   def temp_pressure_snapshot(
       detectors: List[Readable],
       temperature: Movable = inject("sample_temperature"),
       pressure: Movable = inject("sample_pressure"),
       target_temperature: float = 273.0,
       target_pressure: float = 10**5,
       metadata: Optional[Mapping[str, Any]] = None,
   ) -> MsgGenerator:
       """
       Moves devices for pressure and temperature (defaults fetched from the context)
       and captures a single frame from a collection of devices
       Args:
           detectors (List[Readable]): A list of devices to read while the sample is at STP
           temperature (Optional[Movable]): A device controlling temperature of the sample,
               defaults to fetching a device name "sample_temperature" from the context
           pressure (Optional[Movable]): A device controlling pressure on the sample,
               defaults to fetching a device name "sample_pressure" from the context
           target_pressure (Optional[float]): target temperature in Kelvin. Default 273
           target_pressure (Optional[float]): target pressure in Pa. Default 10**5
       Returns:
           MsgGenerator: Plan
       Yields:
           Iterator[MsgGenerator]: Bluesky messages
       """
       yield from move({temperature: target_temperature, pressure: target_pressure})
       yield from count(detectors, 1, metadata or {})
```

### Decorators

Dodal defines a decorator for configuring any `ophyd-async` devices- which will be the majority of devices at Diamond- to write to a common location. 

> **_NOTE:_** **This is an absolute requirement to write data onto the Diamond Filesystem**.  This decorator must be used every time a new data collection is intended to begin. For an example, see below.

```
   @attach_metadata
   def ophyd_async_snapshot(
       detectors: List[Readable],
       metadata: Optional[Mapping[str, Any]] = None,
###    ) -> MsgGenerator:
       Configures a number of devices, which may be Ophyd-Async detectors and require
       knowledge of where to write their files, then takes a snapshot with them.
       Args:
           detectors (List[Readable]): Devices, maybe including Ophyd-Async detectors.
       Returns:
           MsgGenerator: Plan
       Yields:
###            Iterator[MsgGenerator]: Bluesky messages
       yield from count(detectors, 1, metadata or {})

   def repeated_snapshot(
       detectors: List[Readable],
       metadata: Optional[Mapping[str, Any]] = None,
###    ) -> MsgGenerator:
       Configures a number of devices, which may be Ophyd-Async detectors and require
       knowledge of where to write their files, then takes multiple snapshot with them.
       Args:
           detectors (List[Readable]): Devices, maybe including Ophyd-Async detectors.
       Returns:
           MsgGenerator: Plan
       Yields:
###            Iterator[MsgGenerator]: Bluesky messages
       @attach_metadata
       def inner_function():
           yield from count(detectors, 1, metadata or {})


       for _ in range(5):
           yield from inner_function()
```

### Stubs

Some functionality in your plans may make sense to factor out to allow re-use. These pieces of functionality may or may not make sense outside of the context of a plan. Some will, such as nudging a motor, but others may not, such as waiting to consume data from the previous position, or opening a run without an equivalent closure.

To enable blueapi to expose the stubs that it makes sense to, but not the others, blueapi will only expose a subset of `MsgGenerator`\ s under the following conditions:

| `__init__.py` in directory has `__exports__`: List[str]: only
  those named in `__exports__`
| `__init__.py` in directory has `__all__`: List[str] but no
  `__exports__`: only those named in `__all__`

This allows other python packages (such as `plans`) to access every function in `__all__`, while only allowing a subset to be called from blueapi as standalone.

``` 
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
