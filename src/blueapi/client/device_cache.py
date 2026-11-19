from blueapi.service.model import DeviceModel

from .protocols import ClientObjectRef, RestClientProtocol
from .rest import NotFoundError


class DeviceCache:
    """Cache and lazily resolve devices from a Blueapi server."""

    def __init__(self, rest: RestClientProtocol):
        self._rest = rest
        self._cache = {
            model.name: DeviceRef(name=model.name, cache=self, model=model)
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
            device = DeviceRef(name=name, cache=self, model=model)
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

    name: str
    model: DeviceModel
    parent: "DeviceRef | None" = None
    children: dict[str, "DeviceRef"]
    _cache: DeviceCache

    def __init__(
        self,
        name: str,
        cache: DeviceCache,
        model: DeviceModel,
        parent: "DeviceRef | None" = None,
    ):
        self.name = name
        self.model = model
        self._cache = cache
        self.parent = parent
        self.children = {}

    def __getattr__(self, name: str) -> "DeviceRef":
        if name.startswith("_"):
            raise AttributeError(f"No child device named {name}")
        try:
            return self.children[name]
        except KeyError as e:
            raise AttributeError(
                f"{self.name} doesn't have a child named {name}"
            ) from e

    def __dir__(self):
        return [*super().__dir__(), *self.children]

    def __repr__(self):
        return f"Device({self.name})"
