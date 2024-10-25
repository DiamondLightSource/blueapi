from unittest.mock import MagicMock, NonCallableMock

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
    # mock.name must return str, cannot MagicMock(name=name)
    mock = MagicMock()
    mock.name = name
    return mock


def wrong_return_type() -> int:
    return "str"  # type: ignore


fetchable_non_callable = NonCallableMock()
fetchable_callable = MagicMock(return_value="string")

fetchable_non_callable.__name__ = "fetchable_non_callable"
fetchable_non_callable.__module__ = fake_motor_bundle_a.__module__
fetchable_callable.__name__ = "fetchable_callable"
fetchable_callable.__module__ = fake_motor_bundle_a.__module__
