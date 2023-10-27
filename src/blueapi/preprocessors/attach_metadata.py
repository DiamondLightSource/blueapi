import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.utils import make_decorator

from blueapi.core import MsgGenerator
from blueapi.data_management.gda_directory_provider import VisitDirectoryProvider

DATA_SESSION = "data_session"
DATA_GROUPS = "data_groups"


def attach_metadata(
    plan: MsgGenerator,
    provider: VisitDirectoryProvider,
) -> MsgGenerator:
    """
    Attach data session metadata to the runs within a plan and make it correlate
    with an ophyd-async DirectoryProvider.

    This wrapper is meant to ensure (on a best-effort basis) that detectors write
    their data to the same place for a given run, and that their writings are
    tied together in the run via the data_session metadata keyword in the run
    start document.

    The wrapper groups data by staging and bundles it with runs as best it can.
    Since staging is inherently decoupled from runs this is done on a best-effort
    basis. In the following sequence of messages:

    |stage|, stage, |open_run|, close_run, unstage, unstage, |stage|, stage,
    |open_run|, close_run, unstage, unstage

    A new group is created at each |stage| and bundled into the start document
    at each |open_run|.

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
