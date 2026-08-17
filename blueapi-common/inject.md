Ignoring the implementation to start with, there are several options for what
the API/DX should look like.

There are two main options that I can think of for how to pass injected device
information
* Altering the type annotation
  * Works with type checkers
  * Doesn't hide the fact a value is required when running the function directly
    - there is no invalid default value
* Adding a default value
  * Can be added to the end of an argument list after other optional keywords
    * eg `def calibrate(x: int, exposure: float = 2.3, detector=inject("det"))`
      can be called as `calibrate(1, 4.2)` or `calibrate(1, detector=cam3)`

For a plan that looks something like

```python
def custom_plan(x: Movable) -> MsgGenerator:
    pass
```

## Current `inject("name")` function

```python
def foo(x: Movable = inject("foo")): ...
```

This would be the smallest change for existing plans. We could replace the
`inject` function in dodal with a re-export of the new function and everything
would just work™️

If the object to be injected has the same name as the argument, the name could
be omitted, eg `def foo(x: Movable = inject())`. This removes duplication but is
currently not possible as this use is used for composites.

On the downside, even if the type checker can be made to accept it, it doesn't
solve the problem that the argument appears optional but when called directly,
fails later when the type is incorrect.

This approach would continue to be supported, at least in the short term to
allow existing plans to work.

### Inject object as default value

Very similar to the `inject()` function but makes it clear a different mechanism
is being used.

```python
def foo(x: Movable = Inject("bar")): ...
```

## Injected as a generic type

If the injected aspect is included in the type of the parameter, the type
checker doesn't have to be conned via an `Any` returned by `inject()`, there are
no false default parameters and blueapi could introspect the `Injected` type to
access the actual type required.

```python
def foo(x: Injected[Movable]): ...
```

In this case there is no obvious approach to set the name of the device to be
injected if the name is different to the parameter name.

## Annotated with Inject dataclass

Similar to the previous version, we could annotate the existing type with inject
information. This works well with type checkers. It allows non-default names to
be set. It doesn't pretend there is a default argument.

Against that it is very verbose - the majority of the type annotation is now
boilerplate.

```python
def foo(x: Annotated[Movable, Inject(name="foo")]): ...
```

To help slightly, it could be aliased for the case where the name is the same as
the argument name to make it effectively the same as the previous option.

```python
T = TypeVar('T')
Injected = Annotated[T, Inject()]

def foo(x: Injected[Movable]): ...
```

## Annotated with an Inject function call

While not strictly 'correct' in the type checking world, it is possible to use
the result of a function call as an annotation.

```python
def foo(a: Inject(Movable, "bar")): ...
```

Not sure if this could be made to support type checking. Even if it could, I'm
not sure it's clearer or more concise than the previous options.


## Unknowns

* How do positional only args map to schemas?


# Required functionality

## Strings be converted to devices

For the predefined Device types, strings should automatically be converted to
devices.

Not doing this would require every existing plan to be updated and is not
feasible.

## Other types should be injectable if marked

Eg `server: Injected[str]` should allow config to be passed at runtime without
relying on globals

## Defaults can be specified for devices

Even when devices are not in scope it should be possible to define a default.
eg, "use the devices named 'stage_x'".

## Composite devices can be specified

Devices made up of other devices that should be available in the calling
namespace should be available to the plan.

## Components of composite devices should be overridable

If a composite device abc reqiuires 'x', 'y' and 'z', it should be possible to just
specify 'y', eg by `{"abc": {"y": "non-standard"}}`

## Types should match as much as possible

A plan defined as `(mov: Movable[T], pos: T)` should try and deserialize pos to
the correct `T` if the injected `mov` object has a `T` discoverable at runtime,
eg by `get_args`.
