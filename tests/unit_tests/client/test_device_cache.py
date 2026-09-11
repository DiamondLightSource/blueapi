from unittest.mock import MagicMock, Mock

import pytest

from blueapi.client.device_cache import DeviceCache, DeviceRef
from blueapi.service.model import DeviceModel, DeviceResponse


def test_device_cache_ignores_underscores():
    rest = Mock()
    rest.get_devices.return_value = DeviceResponse(
        devices=[
            DeviceModel(name="_ignored", protocols=[]),
        ]
    )
    cache = DeviceCache(rest)
    with pytest.raises(AttributeError, match="_ignored"):
        _ = cache._ignored

    rest.get_devices.reset_mock()
    with pytest.raises(AttributeError, match="_anything"):
        _ = cache._anything
    rest.get_device.assert_not_called()


def test_devices_are_cached(mock_rest):
    cache = DeviceCache(mock_rest)
    _ = cache.foo
    mock_rest.get_device.assert_not_called()
    _ = cache["foo"]
    mock_rest.get_device.assert_not_called()


def test_device_cache_repr(client):
    assert repr(client.devices) == "DeviceCache(2 devices)"


def test_device_repr():
    cache = Mock()
    model = Mock()
    model.name = "foo"
    dev = DeviceRef(cache=cache, model=model)
    assert repr(dev) == "Device(foo)"


def test_device_ignores_underscores():
    cache = MagicMock()
    model = Mock()
    model.name = "foo"
    dev = DeviceRef(cache=cache, model=model)
    with pytest.raises(AttributeError, match="_underscore"):
        _ = dev._underscore
    cache.__getitem__.assert_not_called()
