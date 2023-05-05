from unittest.mock import MagicMock

from ophyd import EpicsMotor


def fake_motor() -> EpicsMotor:
    return _mock_with_name("motor")


def _mock_with_name(name: str) -> MagicMock:
    mock = MagicMock()
    mock.name = name
    return mock
