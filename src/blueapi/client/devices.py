from blueapi.service.model import DeviceModel

from .rest import BlueapiRestClient, NotFoundError


class DeviceCache:
    def __init__(self, rest: BlueapiRestClient):
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


class DeviceRef:
    name: str
    model: DeviceModel
    _cache: DeviceCache

    def __init__(self, name: str, cache: DeviceCache, model: DeviceModel):
        self.name = name
        self.model = model
        self._cache = cache

    def __getattr__(self, name) -> "DeviceRef":
        if name.startswith("_"):
            raise AttributeError(f"No child device named {name}")
        return self._cache[f"{self.name}.{name}"]

    def __repr__(self):
        return f"Device({self.name})"
