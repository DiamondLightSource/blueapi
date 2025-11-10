# Write Bluesky Plans for Blueapi

:::{seealso}
[The bluesky documentation](https://blueskyproject.io/bluesky/main/index.html) for an introduction to bluesky plans and general forms/advice. Blueapi has some additional requirements, which are explained below.
:::

## Format

:::{seealso}
[Explanation of why blueapi treats plans in a special way](../explanations/plans.md)
:::

Plans in Python files look like this:

```{literalinclude} ../../tests/unit_tests/code_examples/plan_module.py
:language: python
```

## Detection

The type annotations in the example above (e.g. `: str`, `: int`, `-> MsgGenerator`) are required as blueapi uses them to detect that this function is intended to be a plan and generate its runtime API. If there is an [`__all__` dunder](https://docs.python.org/3/tutorial/modules.html#importing-from-a-package) present in the module, blueapi will read that and import anything within that qualifies as a plan, per its type annotations. If not it will read everything in the module that hasn't been imported, for example it will ignore a plan imported from another module.

**Input annotations should be as broad as possible**, the least specific implementation that is sufficient to accomplish the requirements of the plan. For example, if a plan is written to drive a specific motor (`MyMotor`), but only uses the general methods on the [`Movable` protocol](https://blueskyproject.io/bluesky/main/hardware.html#bluesky.protocols.Movable), it should take `Movable` as a parameter annotation rather than `MyMotor`.

## Injecting Devices

Some plans are created for specific sets of devices, or will almost always be used with the same devices, it is useful to be able to specify defaults. [Dodal makes this easy with its factory functions](https://diamondlightsource.github.io/dodal/main/how-to/include-devices-in-plans.html).

## Injecting Metadata

The bluesky event model allows for rich structured metadata to be attached to a scan. To enable this to be used consistently, blueapi encourages a standard form.

Plans ([as opposed to stubs](../explanations/plans.md)) **should** include `metadata` as their final parameter, if they do it **must** have the type `dict[str, Any] | None`, [and a default of None](https://stackoverflow.com/questions/26320899/why-is-the-empty-dictionary-a-dangerous-default-value-in-python). If the plan calls to a stub/plan which takes metadata, the plan **must** pass down its metadata, which may be a differently named parameter.

```{literalinclude} ../../tests/unit_tests/code_examples/plan_metadata.py
:language: python
```

## Docstrings

Blueapi exposes the docstrings of plans to clients, along with the parameter types. It is therefore worthwhile to make these detailed and descriptive. This may include units of arguments (e.g. seconds or microseconds), its purpose in the function, the purpose of the plan etc.

```{literalinclude} ../../tests/unit_tests/code_examples/plan_docstrings.py
:language: python
```
