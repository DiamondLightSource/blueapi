# Lifecycle of a Plan

The following demonstrates exactly what the code does with a plan through its lifecycle 
of being written, loaded and run. Take the following plan.


```{literalinclude} ../../tests/unit_tests/code_examples/count_plan.py
:language: python
```

## Loading and Registration

Blueapi will load this plan into its context if configured to load either this module or a module that 
imports it. The `BlueskyContext` will go through all global variables in the module and register them
if it detects that they are plans.

At the point of registration it will inspect the plan's parameters and their type hints, from which it
will build a [pydantic](https://docs.pydantic.dev/) model of the parameters to validate against. In other words, it will build something
like this:

```{literalinclude} ../../tests/unit_tests/code_examples/count_model.py
:language: python
```

This is for illustrative purposes only, this code is not actually generated, but an object resembling this class is constructed in memory. The default arguments will be validated by the context when the plan is run. `my_beamline.det(connect_immediately=False)` evaluates to a lazily created singleton device. The model is also stored in the context.

## Startup

On startup, the context is passed to the worker, which is passed to the service.
The worker also holds a reference to the `RunEngine` that can run the plan.

## Request

A user can send a request to run the plan to the service, which includes values for the parameters.
It takes the form of JSON and may look something like this:
```json
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

The `Service` receives the request and passes it to the worker, which holds it in an internal queue

```
 and passes it to the worker, which holds it in an internal queue
and executes it as soon as it can. 


## Validation

:::{seealso}
[Type Validators](./type_validators.md) for an in-depth explanation of how blueapi knows when to resolve strings as device names 
:::

The pydantic model from earlier, as well as the plan function itself, is loaded out of the registry. The parameter values in the request are validated against the model, this includes looking up devices with names `andor` and `pilatus` or, if detectors was not passed `det`.

## Execution

The validated parameter values are then passed to the plan function, which is passed to the `RunEngine`.
The plan is executed. While it is running, the `Worker` will publish

* Changes to the state of the `RunEngine`
* Changes to any device statuses running within the plan (e.g. when a motor changes position)
* Event model documents emitted by the `RunEngine`
* When the plan starts, finishes or fails.

If an error occurs during any of the stages from "Request" onwards it is sent back to the user
over the message bus.
