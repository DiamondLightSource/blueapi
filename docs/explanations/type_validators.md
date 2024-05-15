# Type Validators

## Requirement

Blueapi takes the parameters of a plan and internally creates a [pydantic](https://docs.pydantic.dev/) model for future validation e.g.
``` 
    def my_plan(a: int, b: str = "b") -> Plan
        ...

    # Internally becomes something like

    class MyPlanModel(BaseModel):
        a: int
        b: str = "b"
```


That way, when the plan parameters are sent in JSON form, they can be parsed and validated by pydantic.
However, it must also cover the case where a plan doesn't take a simple dictionary, list or primitive but
instead a device, such as a detector.

```
    def my_plan(a: int, b: Readable) -> Plan:
        ...
```

An Ophyd object cannot be passed over the network as JSON because it has state.
Instead, a string is passed, representing an ID of the object known to the `BlueskyContext`.
At the time a plan's parameters are validated, blueapi must take all the strings that are supposed
to be devices and look them up against the context. For example with the request:

``` 
    {
        "name": "count",
        "params": {
            "detectors": [
            "andor",
            "pilatus"
            ],
            "num": 3,
            "delay": 0.1
        }
    }
```

`andor` and `pilatus` should be looked up and replaced with Ophyd objects.


## Solution

When the context loads available plans, it iterates through the type signature
and replaces any reference to a bluesky protocol (or instance of a protocol)
with a new class that extends the original type. Defining a class validator on
this new type allows it to check that the string being deserialised is the ID of
a device of the correct type.

These new intermediate types are used only in the deserialisation process. The
object returned from validator method is not checked by pydantic so it can be
the actual instance and the plan never sees the runtime generated reference
type, only the type it was expecting.

> **_NOTE:_** This uses the fact that the new types generated at runtime have access to
    the context that required them via their closure. This circumvents the usual
    problem of pydantic validation not being able to access external state when
    validating or deserialising.

```
    def my_plan(a: int, b: Readable) -> Plan:
        ...

    # Becomes

    class MyPlanModel(BaseModel):
        a: int
        b: Reference[Readable]
```


This also allows `Readable` to be placed at various type levels. For example:
``` 
    def my_weird_plan(
        a: Readable,
        b: List[Readable],
        c: Dict[str, Readable],
        d: List[List[Readable]],
        e: List[Dict[str, Set[Readable]]]) -> Plan:
        ...
```
