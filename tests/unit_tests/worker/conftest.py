from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from ophyd_async.core import PathInfo


@pytest.fixture
def updating_path_provider(tmp_path: Path):
    updating_mock_path_provider = MagicMock()
    updating_mock_path_provider.data_session = AsyncMock(return_value="bar")
    updating_mock_path_provider.update = AsyncMock()
    updating_mock_path_provider.return_value = PathInfo(tmp_path, "foo", 0)
    return updating_mock_path_provider
