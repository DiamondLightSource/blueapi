# Configure Detectors to Write Files

Dodal defines a decorator for configuring any `ophyd-async` devices- which will be the majority of devices at Diamond- to write to a common location. 

> **_NOTE:_** **This is an absolute requirement to write data onto the Diamond Filesystem**.  This decorator must be used every time a new data collection is intended to begin. For an example, see below.

```
   @attach_metadata
   def ophyd_async_snapshot(
       detectors: List[Readable],
       metadata: Optional[Mapping[str, Any]] = None,
###    ) -> MsgGenerator:
       Configures a number of devices, which may be Ophyd-Async detectors and require
       knowledge of where to write their files, then takes a snapshot with them.
       Args:
           detectors (List[Readable]): Devices, maybe including Ophyd-Async detectors.
       Returns:
           MsgGenerator: Plan
       Yields:
###            Iterator[MsgGenerator]: Bluesky messages
       yield from count(detectors, 1, metadata or {})

   def repeated_snapshot(
       detectors: List[Readable],
       metadata: Optional[Mapping[str, Any]] = None,
###    ) -> MsgGenerator:
       Configures a number of devices, which may be Ophyd-Async detectors and require
       knowledge of where to write their files, then takes multiple snapshot with them.
       Args:
           detectors (List[Readable]): Devices, maybe including Ophyd-Async detectors.
       Returns:
           MsgGenerator: Plan
       Yields:
###            Iterator[MsgGenerator]: Bluesky messages
       @attach_metadata
       def inner_function():
           yield from count(detectors, 1, metadata or {})


       for _ in range(5):
           yield from inner_function()
```
