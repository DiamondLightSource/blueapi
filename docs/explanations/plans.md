# Plans

While the bluesky project uses `plan` in a general sense to refer to any `Iterable` of `Msg`'s which may be run by the `RunEngine`, blueapi distinguishes between a `plan` and a `stub`. This distinction is made to allow for a subset of `stub`'s to be exposed and run, as `stub`'s may not make sense to run alone.

Generally, a `plan` includes at least one `open_run` and `close_run` and is a complete description of an experiment. If it does not, it is a `stub`. This distinction is made in the bluesky core library between the `plan`'s and `plan_stub`'s modules.


## Allowed Argument Types

When added to the blueapi context, `PlanGenerator`'s are formalised into their schema - [a Pydantic BaseModel](https://docs.pydantic.dev/2.10/concepts/models/) with the expected argument types and their defaults. 

Therefore, `PlanGenerator`'s must only take as arguments [those types which are valid Pydantic fields](https://docs.pydantic.dev/dev/concepts/types) or Device types which implement `BLUESKY_PROTOCOLS` defined in dodal, which are fetched from the context at runtime.

Allowed argument types for Pydantic BaseModels include the primitives, types that extend `BaseModel` and `dict`'s, `list`'s  and other `sequence`'s of supported types. Blueapi will deserialize these types from JSON, so `dict`'s must use `str` keys.

## Positional, Keyword and Variadic Arguments

A plan can use every kind of Python parameter: positional-only, positional-or-keyword, variadic positional (`*args`), keyword-only and variadic keyword (`**kwargs`).

```{literalinclude} ../../tests/unit_tests/code_examples/plan_argument_kinds.py
:language: python
```

A request to run a plan carries a list of positional arguments, `args`, and a mapping of keyword arguments, `params`. Blueapi binds them to the plan's parameters in the same way that Python binds the arguments of a function call, then validates each value against its type annotation. For example, this request:

```json
{
    "name": "repeated_read",
    "args": [3, 0.5, "det1", "det2"],
    "params": {"wait": true, "sample": "silicon"},
    "instrument_session": "cm12345-1"
}
```

runs `repeated_read(3, 0.5, det1, det2, wait=True, sample="silicon")`, where `det1` and `det2` are the devices with those names.

The rules are the same as for a Python call:

- Positional-only parameters, such as `repeats`, must be passed in `args`.
- Keyword-only parameters, such as `wait`, must be passed in `params`.
- Any other parameter, such as `delay`, can be passed in either, but not in both.
- Values in `args` beyond the named parameters are collected by `*args`, and entries in `params` that match no other parameter are collected by `**kwargs`. A plan that does not declare them cannot accept extra arguments.

Blueapi rejects a request that breaks these rules, or whose values do not match the annotations, when it is submitted.

From the command line, pass the positional arguments as a JSON array with `--args`, alongside the JSON object of keyword arguments:

```
blueapi controller run -i cm12345-1 --args '[3, 0.5, "det1", "det2"]' repeated_read '{"wait": true, "sample": "silicon"}'
```

The Python client passes the positional and keyword arguments of a call straight through to the server.

In the schema that blueapi publishes for a plan, `*args` appears as an array and `**kwargs` as an object, each named after its parameter.

### Type annotations are required

Every parameter of a plan must have a type annotation, and this includes `*args` and `**kwargs`. As usual in Python, the annotation on a variadic parameter is the type of each individual value: `*detectors: Readable` accepts any number of devices, and `**labels: str` accepts any number of named strings.

The annotation is also what tells blueapi how to convert each value from its JSON form, for example from a device name to the device.

:::{warning}
`Any` does not mean "any Python object", and a parameter annotated with `Any` cannot be passed a device. Blueapi has no type to convert the value to, so the plan receives it exactly as it arrived in the JSON request: a `str`, `int`, `float`, `bool`, `None`, `list` or `dict`. A device name stays a string and a dictionary is not converted into a model. The same applies to values inside `list[Any]` and `dict[str, Any]`, and to `*args: Any` and `**kwargs: Any`.

To receive a device, annotate the parameter with the device's type or with a bluesky protocol such as `Readable`. To receive a device when one is available and its name otherwise, see [Devices That May Not Be Available](#devices-that-may-not-be-available).
:::

A plan with an unannotated parameter cannot be loaded:

```{literalinclude} ../../tests/unit_tests/code_examples/invalid_plan_args.py
:language: python
```

Loading the module that contains this plan fails with `ValueError: Type annotation is required for 'args' in 'demo'`. Plans are loaded when the environment starts, so the error stops the whole environment from initializing, not only this plan.

(devices-that-may-not-be-available)=
## Devices That May Not Be Available

A parameter annotated with a device type alone, such as `Readable`, must be given the name of a device of that type. Blueapi rejects the request otherwise. If a plan can do something sensible without the device, annotate the parameter with a union of the device type and `str`:

```{literalinclude} ../../tests/unit_tests/code_examples/plan_optional_device.py
:language: python
```

Blueapi passes the device if one with that name and type is available. Otherwise it passes the name through unchanged, as a string. This happens both when no device has that name and when a device has the name but is not of the annotated type.

The device type must come first in the union. With `str | Readable` the name is never looked up and the plan always receives a string.

A plan written this way cannot assume that it has a device, so it must check with `isinstance` before using the value, as the example does. Make the check at the start of the plan, before any hardware is moved or a run is opened, and log the outcome so that a missing device is noticed instead of being silently skipped.

The same applies to each value of a variadic parameter and to each item of a container: `*detectors: Readable | str` and `list[Readable | str]` can both receive a mixture of devices and strings. A union with `Any`, such as `Readable | Any`, resolves names in the same way and also accepts values that are not strings.

## Exporting with `__all__`

Blueapi will observe `__all__` and only import plans defined there

```{literalinclude} ../../tests/unit_tests/code_examples/deferred_plans.py
:language: python
```
