from typing import Any, Type
from unittest.mock import MagicMock

import pytest

from blueapi.core import BLUESKY_PROTOCOLS, create_bluesky_protocol_conversions


@pytest.mark.parametrize("a_type", BLUESKY_PROTOCOLS)
def test_creates_resolver_for(a_type: Type[Any]):
    converters = create_bluesky_protocol_conversions(MagicMock())
    target_types = map(lambda c: c.target, converters)
    assert a_type in list(target_types)
