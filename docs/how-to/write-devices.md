# Write Devices for Blueapi

:::{seealso}
[Home of Plans and Devices](../explanations/extension-code.md) for information about where device code usually lives.
:::


## Format

:::{seealso}
[Dodal](https://github.com/DiamondLightSource/dodal) for many more examples
:::

Devices are made using the [dodal](https://github.com/DiamondLightSource/dodal) style available through factory functions like this:

```python 
from my_facility_devices import MyTypeOfDetector

def my_detector(name: str) -> MyTypeOfDetector:
    return MyTypeOfDetector(name, {"other_config": "foo"})
```

The return type annotation `-> MyTypeOfDetector` is required as blueapi uses it to determine that this function creates a device. Meaning you can have a Python file where only some functions create devices and they will be automatically picked up. Similarly, these functions can be organized per-preference into files. 

The device is created via a function rather than a global to preserve side-effect-free imports. Each device must have its own factory function.

# How to Configure Detectors to Write Files

:::{note}
**This is an absolute requirement to write data onto the Diamond Filesystem**. This decorator must be used every time a new data collection is intended to begin. For an example, see below.
:::

Dodal defines a decorator, `@attach_data_session_metadata_decorator()`, for configuring `ophyd-async` detectors to write data to a common location. 

```python
   @attach_metadata
   def ophyd_async_snapshot(
       detectors: List[Readable],
       metadata: Optional[dict[str, Any]] = None,
       ) -> MsgGenerator:
       Configures a number of devices, which may be Ophyd-Async detectors and require
       knowledge of where to write their files, then takes a snapshot with them.
       Args:
           detectors (List[Readable]): Devices, maybe including Ophyd-Async detectors.
       Returns:
           MsgGenerator: Plan
       Yields:
               Iterator[MsgGenerator]: Bluesky messages
       yield from count(detectors, 1, metadata or {})

   def repeated_snapshot(
       detectors: List[Readable],
       metadata: Optional[dict[str, Any]] = None,
       ) -> MsgGenerator:
       Configures a number of devices, which may be Ophyd-Async detectors and require
       knowledge of where to write their files, then takes multiple snapshot with them.
       Args:
           detectors (List[Readable]): Devices, maybe including Ophyd-Async detectors.
       Returns:
           MsgGenerator: Plan
       Yields:
               Iterator[MsgGenerator]: Bluesky messages
       @attach_metadata
       def inner_function():
           yield from count(detectors, 1, metadata or {})


       for _ in range(5):
           yield from inner_function()
```
