import asyncio
import logging
from contextlib import suppress
from typing import Any, Dict, Iterable

from ophyd_async.core import DEFAULT_TIMEOUT
from ophyd_async.core import Device as OphydAsyncDevice
from ophyd_async.core import NotConnected


async def connect_ophyd_async_devices(
    devices: Iterable[Any],
    sim: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> None:
    tasks: Dict[asyncio.Task, str] = {}
    for device in devices:
        if isinstance(device, OphydAsyncDevice):
            task = asyncio.create_task(device.connect(sim=sim))
            tasks[task] = device.name
    if tasks:
        await _wait_for_tasks(tasks, timeout=timeout)


async def _wait_for_tasks(tasks: Dict[asyncio.Task, str], timeout: float):
    done, pending = await asyncio.wait(tasks, timeout=timeout)
    if pending:
        msg = f"{len(pending)} Devices did not connect:"
        for t in pending:
            t.cancel()
            with suppress(Exception):
                await t
            e = t.exception()
            msg += f"\n  {tasks[t]}: {type(e).__name__}"
            lines = str(e).splitlines()
            if len(lines) <= 1:
                msg += f": {e}"
            else:
                msg += "".join(f"\n    {line}" for line in lines)
        logging.error(msg)
    raised = [t for t in done if t.exception()]
    if raised:
        logging.error(f"{len(raised)} Devices raised an error:")
        for t in raised:
            logging.exception(f"  {tasks[t]}:", exc_info=t.exception())
    if pending or raised:
        raise NotConnected("Not all Devices connected")
