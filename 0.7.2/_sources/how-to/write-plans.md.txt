# Write Bluesky Plans for Blueapi

:::{seealso}
[The bluesky documentation](https://blueskyproject.io/bluesky/main/index.html) for an introduction to bluesky plans and general forms/advice. Blueapi has some additional requirements, which are explained below.
:::

## Format

:::{seealso}
[Explanation of why blueapi treats plans in a special way](../explanations/plans.md)
:::

Plans in Python files look like this:

```python 
from bluesky.protocols import Readable, Movable
from bluesky.utils import MsgGenerator
from typing import Mapping, Any

def my_plan(
    detector: Readable, 
    motor: Movable, 
    steps: int, 
    sample_name: str, 
    extra_metadata: dict[str, Any]) -> MsgGenerator:
    
    # logic goes here
    ...
```

The type annotations (e.g. `: str`, `: int`, `-> MsgGenerator`) are required as blueapi uses them to detect that this function is intended to be a plan and generate its runtime API.

**Input annotations should be as broad as possible**, the least specific implementation that is sufficient to accomplish the requirements of the plan. For example, if a plan is written to drive a specific motor (`MyMotor`), but only uses the general methods on the [`Movable` protocol](https://blueskyproject.io/bluesky/main/hardware.html#bluesky.protocols.Movable), it should take `Movable` as a parameter annotation rather than `MyMotor`.

## Injecting Devices

Some plans are created for specific sets of devices, or will almost always be used with the same devices, it is useful to be able to specify defaults. [Dodal makes this easy with its factory functions](https://diamondlightsource.github.io/dodal/main/how-to/include-devices-in-plans.html).

## Injecting Metadata

The bluesky event model allows for rich structured metadata to be attached to a scan. To enable this to be used consistently, blueapi encourages a standard form.

Plans ([as opposed to stubs](../explanations/plans.md)) **should** include `metadata` as their final parameter, if they do it **must** have the type `dict[str, Any] | None`, [and a default of None](https://stackoverflow.com/questions/26320899/why-is-the-empty-dictionary-a-dangerous-default-value-in-python). If the plan calls to a stub/plan which takes metadata, the plan **must** pass down its metadata, which may be a differently named parameter.

```python
def pass_metadata(x: Movable, metadata: dict[str, Any] | None = None) -> MsgGenerator:
    yield from bp.count{[x], md=metadata or {}}
```

## Docstrings

Blueapi exposes the docstrings of plans to clients, along with the parameter types. It is therefore worthwhile to make these detailed and descriptive. This may include units of arguments (e.g. seconds or microseconds), its purpose in the function, the purpose of the plan etc.

```python
def temp_pressure_snapshot(
    detectors: List[Readable],
    temperature: Movable = sample_temperature(),
    pressure: Movable = sample_pressure(),
    target_temperature: float = 273.0,
    target_pressure: float = 10**5,
    metadata: Optional[dict[str, Any]] = None,
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
