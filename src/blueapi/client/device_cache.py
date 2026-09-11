from blueapi.service.model import DeviceModel

from .protocols import ClientObjectRef, RestClientProtocol
from .rest import NotFoundError


class DeviceCache:
    """Cache and lazily resolve devices from a Blueapi server."""

    def __init__(self, rest: RestClientProtocol):
        self._rest = rest
        self._cache = {
            model.name: DeviceRef(cache=self, model=model)
            for model in rest.get_devices().devices
        }
        for name, device in self._cache.items():
            if name.startswith("_"):
                continue
            setattr(self, name, device)

    def __getitem__(self, name: str) -> "DeviceRef":
        """Get a device by name, fetching it from the server if necessary.

        Cached devices are returned directly. If the device has not yet been
        cached, it is retrieved from the server and added to the cache.

        Args:
            name: The fully-qualified name of the device.

        Returns:
            A reference to the requested device.

        Raises:
            AttributeError: If no device with the given name exists.
        """
        if dev := self._cache.get(name):
            return dev
        try:
            model = self._rest.get_device(name)
            device = DeviceRef(cache=self, model=model)
            self._cache[name] = device
            setattr(self, model.name, device)
            return device
        except NotFoundError as e:
            raise AttributeError(f"No device named '{name}' available") from e

    def __getattr__(self, name: str) -> "DeviceRef":
        if name.startswith("_"):
            return super().__getattribute__(name)
        return self[name]

    def __iter__(self):
        return iter(self._cache.values())

    def __repr__(self) -> str:
        return f"DeviceCache({len(self._cache)} devices)"


class DeviceRef(ClientObjectRef):
    """Reference to a device exposed by Blueapi.

    Child devices can be accessed using attribute-style access, for example
    ``devices.my_device.child``.
    """

    model: DeviceModel
    _cache: DeviceCache

    def __init__(self, cache: DeviceCache, model: DeviceModel):
        self.model = model
        self._cache = cache

    def __getattr__(self, name) -> "DeviceRef":
        if name.startswith("_"):
            raise AttributeError(f"No child device named {name}")
        return self._cache[f"{self.model.name}.{name}"]

    def __repr__(self):
        return f"Device({self.model.name})"
