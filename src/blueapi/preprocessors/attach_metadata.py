import bluesky.preprocessors as bpp
from bluesky.utils import make_decorator
from ophyd_async.core import DirectoryProvider

from blueapi.core import MsgGenerator

DATA_SESSION = "data_session"
DATA_GROUPS = "data_groups"


def attach_metadata(
    plan: MsgGenerator,
    provider: DirectoryProvider,
) -> MsgGenerator:
    """
    Attach data session metadata to the runs within a plan and make it correlate
    with an ophyd-async DirectoryProvider.

    This calls the directory provider and ensures the start document contains
    the correct data session.

    Args:
        plan: The plan to preprocess
        provider: The directory provider that participating detectors are aware of.

    Returns:
        MsgGenerator: A plan

    Yields:
        Iterator[Msg]: Plan messages
    """
    directory_info = provider()
    yield from bpp.inject_md_wrapper(
        plan, md={DATA_SESSION: directory_info.filename_prefix}
    )


attach_metadata_decorator = make_decorator(attach_metadata)
