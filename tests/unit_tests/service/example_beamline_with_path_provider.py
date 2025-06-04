from pathlib import Path

from dodal.common.beamlines.beamline_utils import (
    set_path_provider,
)
from dodal.common.visit import LocalDirectoryServiceClient, StaticVisitPathProvider

BL = "test"

set_path_provider(
    StaticVisitPathProvider(
        BL,
        Path("/tmp"),
        client=LocalDirectoryServiceClient(),
    )
)
