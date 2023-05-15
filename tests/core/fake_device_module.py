from unittest.mock import MagicMock

from ophyd import EpicsMotor


def fake_motor_bundle_b(
    fake_motor_x: EpicsMotor,
    fake_motor_y: EpicsMotor,
) -> EpicsMotor:
    return _mock_with_name("motor_bundle_b")


def fake_motor_x() -> EpicsMotor:
    return _mock_with_name("motor_x")


def fake_motor_y() -> EpicsMotor:
    return _mock_with_name("motor_y")


def fake_motor_bundle_a(
    fake_motor_x: EpicsMotor,
    fake_motor_y: EpicsMotor,
) -> EpicsMotor:
    return _mock_with_name("motor_bundle_a")


def _mock_with_name(name: str) -> MagicMock:
    mock = MagicMock()
    mock.name = name
    return mock
