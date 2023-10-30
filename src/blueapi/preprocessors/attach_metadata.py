import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.utils import make_decorator

from blueapi.core import MsgGenerator
from blueapi.data_management.visit_directory_provider import VisitDirectoryProvider

DATA_SESSION = "data_session"
DATA_GROUPS = "data_groups"


def attach_metadata(
    plan: MsgGenerator,
    provider: VisitDirectoryProvider,
) -> MsgGenerator:
    """
    Attach data session metadata to the runs within a plan and make it correlate
    with an ophyd-async DirectoryProvider.

    This updates the directory provider (which in turn makes a call to to a service
    to figure out which scan number we are using for such a scan), and ensures the
    start document contains the correct data session.

    Args:
        plan: The plan to preprocess
        provider: The directory provider that participating detectors are aware of.

    Returns:
        MsgGenerator: A plan

    Yields:
        Iterator[Msg]: Plan messages
    """
    yield from bps.wait_for([provider.update])
    directory_info = provider()
    yield from bpp.inject_md_wrapper(
        plan, md={DATA_SESSION: directory_info.filename_prefix}
    )


attach_metadata_decorator = make_decorator(attach_metadata)
