# Plans

While the bluesky project uses `plan` in a general sense to refer to any `Iterable` of `Msg`'s which may be run by the `RunEngine`, blueapi distinguishes between a `plan` and a `stub`. This distinction is made to allow for a subset of `stub`'s to be exposed and run, as `stub`'s may not make sense to run alone.

Generally, a `plan` includes at least one `open_run` and `close_run` and is a complete description of an experiment. If it does not, it is a `stub`. This distinction is made in the bluesky core library between the `plan`'s and `plan_stub`'s modules.


## Allowed Argument Types

When added to the blueapi context, `PlanGenerator`'s are formalised into their schema - [a Pydantic BaseModel](https://docs.pydantic.dev/2.10/concepts/models/) with the expected argument types and their defaults. 

Therefore, `PlanGenerator`'s must only take as arguments [those types which are valid Pydantic fields](https://docs.pydantic.dev/dev/concepts/types) or Device types which implement `BLUESKY_PROTOCOLS` defined in dodal, which are fetched from the context at runtime.

Allowed argument types for Pydantic BaseModels include the primitives, types that extend `BaseModel` and `dict`'s, `list`'s  and other `sequence`'s of supported types. Blueapi will deserialize these types from JSON, so `dict`'s must use `str` keys.

### Disallowed Plan arguments

Positional-only arguments are not supported because plan parameters are passed as keyword arguments.

Example of unsupported plan arguments

```{literalinclude} ../../tests/unit_tests/code_examples/invalid_plan_args.py
:language: python
```

When blueapi is told to run this plan it will raise `TypeError: demo() got some positional-only arguments passed as keyword arguments: 'foo'`.

> **Note**: Variadic arguments like `*args`, `**kwargs` are also disallowed plan arguments.

## Exporting with `__all__`

Blueapi will observe `__all__` and only import plans defined there

```{literalinclude} ../../tests/unit_tests/code_examples/deferred_plans.py
:language: python
```
