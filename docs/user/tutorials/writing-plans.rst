Writing bluesky plans for blueapi
=================================

**Please read the following completely and carefully, as you risk losing data if plans are written incorrectly.**.

For an introduction to bluesky plans and general forms/advice, `see the
bluesky documentation <https://nsls-ii.github.io/bluesky/plans.html>`__.
Blueapi has some additional requirements, which are explained below.

Generally, if a ``MsgGenerator`` includes at least one
``open_run`` and ``close_run``, it is a ``plan``, a complete description
of an experiment. If it does not, it is a ``stub``.

Plans
~~~~~

A ``plan`` is a complete data collection proceedure.

Type Annotations
^^^^^^^^^^^^^^^^

“Plans” in the bluesky context are any iterable of ``Msg`` instructions,
but in the context of blueapi are ``PlanGenerator``\ s: functions that
take any arguments and return a ``MsgGenerator`` (a python ``Generator``
that yields ``Msg``\ s). **These ``PlanGenerator``\ s must be annotated
with the return type ``MsgGenerator`` to be added to the blueapi
context**.

.. code:: python

   def plan() -> MsgGenerator:
       # The minimum plan acceptable to blueapi
       yield from {}

**Plan arguments should be annotated**, which will enable use of the
schema generated for each plan, and enables checking the arguments are
valid. **Input annotations should be as broad as possible**, the least
specific implementation that is sufficient to accomplish the
requirements of the plan, as this will allow re-use of the behaviour.

For example, if a plan is written to drive a specific implementation of
Movable, but never calls any methods on the device and only yields
bluesky ``'set'`` Msgs, it can be generalised to instead use the base
protocol ``Movable``.

.. code:: python

   def move_to_each_position(axis: Movable) -> MsgGenerator:
       # Originally written for SpecificImplementationMovable
       for _ in range(i):
           yield from abs_set(axis, location)

Injecting defaults
^^^^^^^^^^^^^^^^^^

Often when writing a plan, it is known which device the plan will mostly
or always be run with, but at the time of writing the plan the device
object has not been instantiated: dodal defines device factory
functions, but these cannot be injected as default arguments to plans.

Importing ``inject`` from dls-bluesky-core, which fetches the device from the
blueapi context when the plan is imported allows defaulting devices, so
long as there is a device of that name in the context, and it complies
to the type annotation of the function.

.. code:: python

   def touch_synchrotron(sync: Synchrotron = inject("synchrotron")) -> MsgGenerator:
       # There is only one Synchrotron device, so we know which one it will always be.
       # If there is no device named "synchrotron" in the blueapi context, it will except.
       sync.specific_function()
       yield from {}

Metadata
^^^^^^^^

The bluesky event model allows for rich structured metadata to be
attached to a scan. To enable this to be used consistently, a standard
for attach metadata to a plan is **plans should include ``metadata`` as
their final argument, which must have the type Optional[Mapping[str,
Any]],**\ `and a default of
None <https://stackoverflow.com/questions/26320899/why-is-the-empty-dictionary-a-dangerous-default-value-in-python>`__\ **,
with the plan defaulting to an empty dict if passed None. If the plan
calls to a stub/plan which takes metadata, the plan should pass down its
metadata, which may be a differently named argument**.

.. code:: python

   def pass_metadata(x: Movable, metadata: Optional[Mapping[str, Any]] = None) -> MsgGenerator:
       yield from bp.count{[x], md=metadata or {}}

Docstrings
^^^^^^^^^^

When importing plans blueapi constructs a context and schemas, which
includes the docstrings of imported Plans. **These should therefore
explain as much about the scan as cannot be ascertained from its
arguments and name**. This may include units of arguments (e.g. seconds
or microseconds), its purpose in the function, the purpose of the plan
etc.

.. code:: python

   def temp_pressure_snapshot(
       detectors: List[Readable],
       temperature: Movable = inject("sample_temperature"),
       pressure: Movable = inject("sample_pressure"),
       target_temperature: float = 273.0,
       target_pressure: float = 10**5,
       metadata: Optional[Mapping[str, Any]] = None,
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

Decorators
^^^^^^^^^^

dls-bluesky-core defines a decorator for configuring any ``ophyd-async`` devices,
which will be the majority of devices at Diamond, to write to a common
location. **This is an absolute requirement to write data onto the
Diamond Filesystem**.

**This decorator must be used every time a new data collection is
intended to begin. For an example, see below**.

.. code:: python

   @attach_metadata
   def ophyd_async_snapshot(
       detectors: List[Readable],
       metadata: Optional[Mapping[str, Any]] = None,
   ) -> MsgGenerator:
       """
       Configures a number of devices, which may be Ophyd-Async detectors and require
       knowledge of where to write their files, then takes a snapshot with them.
       Args:
           detectors (List[Readable]): Devices, maybe including Ophyd-Async detectors.
       Returns:
           MsgGenerator: Plan
       Yields:
           Iterator[MsgGenerator]: Bluesky messages
       """
       yield from count(detectors, 1, metadata or {})

   def repeated_snapshot(
       detectors: List[Readable],
       metadata: Optional[Mapping[str, Any]] = None,
   ) -> MsgGenerator:
       """
       Configures a number of devices, which may be Ophyd-Async detectors and require
       knowledge of where to write their files, then takes multiple snapshot with them.
       Args:
           detectors (List[Readable]): Devices, maybe including Ophyd-Async detectors.
       Returns:
           MsgGenerator: Plan
       Yields:
           Iterator[MsgGenerator]: Bluesky messages
       """
       @attach_metadata
       def inner_function():
           yield from count(detectors, 1, metadata or {})


       for _ in range(5):
           yield from inner_function()

Stubs
~~~~~

Some functionality in your plans may make sense to factor out to allow
re-use. These pieces of functionality may or may not make sense outside
of the context of a plan. Some will, such as nudging a motor, but others
may not, such as waiting to consume data from the previous position, or
opening a run without an equivalent closure.

To enable blueapi to expose the stubs that it makes sense to, but not
the others, blueapi will only expose a subset of ``MsgGenerator``\ s
under the following conditions:

| ``__init__.py`` in directory has ``__exports__``: List[str]: only
  those named in ``__exports__``
| ``__init__.py`` in directory has ``__all__``: List[str] but no
  ``__exports__``: only those named in ``__all__``

This allows other python packages (such as ``plans``) to access every
function in ``__all__``, while only allowing a subset to be called from
blueapi as standalone.