from typing import List

import bluesky.plan_stubs as bps
from bluesky.utils import make_decorator
from ophyd_async.detector import DirectoryInfo, DirectoryProvider

from blueapi.core import MsgGenerator


class GDADirectoryProvider(DirectoryProvider):
    def __init__(self, url: str, visit_id: str) -> None:
        ...

    def __call__(self) -> DirectoryInfo:
        return super().__call__()

    async def update(self) -> None:
        ...


DATA_SESSION = "data_session"
DATA_GROUPS = "data_groups"


def attach_metadata(
    data_groups: List[str],
    provider: GDADirectoryProvider,
    plan: MsgGenerator,
) -> MsgGenerator:
    """Updates a directory provider default location for file storage."""
    staging = False

    messages = list(plan)
    will_write_data = "open_run" in [msg.command for msg in messages]
    remade_plan = (msg for msg in messages)

    for message in remade_plan:
        if (message.command == "stage") and (not staging and will_write_data):
            yield from bps.wait_for([provider.update])
            staging = True

        if message.command == "open_run":
            message.kwargs[DATA_SESSION] = provider().filename_prefix
            message.kwargs[DATA_GROUPS] = data_groups

        yield message


attach_metadata_decorator = make_decorator(attach_metadata)
