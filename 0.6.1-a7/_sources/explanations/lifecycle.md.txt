# Lifecycle of a Plan

The following demonstrates exactly what the code does with a plan through its lifecycle 
of being written, loaded and run. Take the following plan.
```
    from typing import Any, List, Mapping, Optional, Union
    
    import bluesky.plans as bp
    from bluesky.utils import MsgGenerator
    from dodal.common import inject
    from bluesky.protocols import Readable
    
    
    def count(
        detectors: List[Readable] = [inject("det")],  # default valid for Blueapi only
        num: int = 1,
        delay: Optional[Union[float, List[float]]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> MsgGenerator:
        """
        Take `n` readings from a collection of detectors
    
        Args:
            detectors (List[Readable]): Readable devices to read: when being run in Blueapi
                                        defaults to fetching a device named "det" from its
                                        context, else will require to be overridden.
            num (int, optional): Number of readings to take. Defaults to 1.
            delay (Optional[Union[float, List[float]]], optional): Delay between readings.
                                                                Defaults to None.
            metadata (Optional[Mapping[str, Any]], optional): Key-value metadata to include
                                                            in exported data.
                                                            Defaults to None.
    
        Returns:
            MsgGenerator: _description_
    
        Yields:
            Iterator[MsgGenerator]: _description_
        """
    
        yield from bp.count(detectors, num, delay=delay, md=metadata)
```


## Loading and Registration

Blueapi will load this plan into its context if configured to load either this module or a module that 
imports it. The `BlueskyContext` will go through all global variables in the module and register them
if it detects that they are plans.

At the point of registration it will inspect the plan's parameters and their type hints, from which it
will build a [pydantic](https://docs.pydantic.dev/) model of the parameters to validate against. In other words, it will build something
like this:


```
    from pydantic import BaseModel

    class CountParameters(BaseModel):
        detectors: List[Readable] = ["det"]
        num: int = 1
        delay: Optional[Union[float, List[float]]] = None
        metadata: Optional[Mapping[str, Any]] = None

        class Config:
            arbitrary_types_allowed = True
            validate_all = True

    This is for illustrative purposes only, this code is not actually generated, but an object
    resembling this class is constructed in memory.
    The default arguments will be validated by the context to inject the "det" device when the
    plan is run. The existence of the "det" default device is not checked until this time.
```

The model is also stored in the context.


## Startup

On startup, the context is passed to the worker, which is passed to the service.
The worker also holds a reference to the `RunEngine` that can run the plan.


## Request

A user can send a request to run the plan to the service, which includes values for the parameters.
It takes the form of JSON and may look something like this:
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

The `Service` receives the request and passes it to the worker, which holds it in an internal queue
and executes it as soon as it can. 


## Validation

The pydantic model from earlier, as well as the plan function itself, is loaded out of the registry
The parameter values in the request are validated against the model, this includes looking up devices
with names `andor` and `pilatus` or, if detectors was not passed `det`.

See also [type validators](./type_validators.md)


## Execution

The validated parameter values are then passed to the plan function, which is passed to the RunEngine.
The plan is executed. While it is running, the `Worker` will publish

* Changes to the state of the `RunEngine`
* Changes to any device statuses running within a plan (e.g. when a motor changes position)
* Event model documents emitted by the `RunEngine`
* When a plan starts, finishes or fails.

If an error occurs during any of the stages from "Request" onwards it is sent back to the user
over the message bus.
