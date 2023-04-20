Type Validators
===============

Requirement
-----------

Blueapi takes the parameters of a plan and internally creates a pydantic_ model for future validation e.g.

.. code:: python

    def my_plan(a: int, b: str = "b") -> Plan
        ...

    # Internally becomes something like

    class MyPlanModel(BaseModel):
        a: int
        b: str = "b"


That way, when the plan parameters are send in JSON form, they can be parsed and validated by pydantic. 
However, it must also cover the case where a plan doesn't take a simple dictionary, list or primitive but 
instead a device, such as a detector. 

.. code:: python

    def my_plan(a: int, b: Readable) -> Plan:
        ...


An Ophyd object cannot be passed over the network as JSON because it has state. 
Instead, a string is passed, representing an ID of the object known to the ``BlueskyContext``.
At the time a plan's parameters are validated, blueapi must take all the strings that are supposed
to be devices and look them up against the context. For example with the request:

.. code:: json

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

``andor`` and ``pilatus`` should be looked up and replaced with Ophyd objects.


Solution
--------

Before pydantic, blueapi used apischema_, which had an ideal feature for this called conversions_.
Currently in the utils module of a blueapi is a similar feature called type validators.

They enable the ``BlueskyContext`` to dynamically generate pydantic models, like above, that look 
roughly like this:

.. code:: python
    
    def my_plan(a: int, b: Readable) -> Plan:
        ...

    # Becomes

    class MyPlanModel(BaseModel):
        a: int
        b: Readable

        @validator("b")
        def valdiate_b(self, val: str) -> Readable:
            return ctx.find_device(val)


It also handles the case of the ``Readable`` type being placed at various type levels? For example:

.. code:: python
    
    def my_weird_plan(
        a: Readable, 
        b: List[Readable], 
        c: Dict[str, Readable], 
        d: List[List[Readable]], 
        e: List[Dict[str, Set[Readable]]]) -> Plan:
        ...


Implementation Details
----------------------

Pydantic models have validators: functions that are applied to specific fields by name. This is
insufficient for the requirements here, it would be helpful if validators could be applied by type, 
rather than name.
The type validation module is essentially a shim layer that works out the names of all fields of a
particular type, then creates validators for all of those names. It also supports the type being in
nested lists and/or dictionaries, as mentioned above.
The field names are deteted by comparing the type annotation in the model to the type requested.
The actual validator is a function supplied by the caller, but if a list or dictionary is passed,
it will apply it to each item/value.

.. _pydantic: https://docs.pydantic.dev/
.. _apischema: https://wyfo.github.io/apischema/0.18/
.. _conversions: https://wyfo.github.io/apischema/0.18/conversions/