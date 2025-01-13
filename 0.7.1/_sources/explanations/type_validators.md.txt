# Type Validators

When the `context` loads available plans, it iterates through the type signature and replaces any reference to a bluesky protocol with a new class that extends the original type. Defining a class validator on this new type allows it to check that the string being deserialised is the ID of a device of the correct type.

These new intermediate types are used only in the deserialisation process. The object returned from validator method is not checked by pydantic so it can be the actual instance and the plan never sees the runtime generated reference type, only the type it was expecting.

:::{note}
This uses the fact that the new types generated at runtime have access to the context that required them via their closure. This circumvents the usual problem of pydantic validation not being able to access external state when validating or deserializing.
:::

```python
def my_plan(a: int, b: Readable) -> Plan:
    ...

# Becomes

class MyPlanModel(BaseModel):
    a: int
    b: Reference[Readable]
```

This also allows `Readable` to be placed at various type levels. For example:
```python
def my_weird_plan(
    a: Readable,
    b: List[Readable],
    c: Dict[str, Readable],
    d: List[List[Readable]],
    e: List[Dict[str, Set[Readable]]]) -> Plan:
    ...
```
