from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DeviceConnectResult(Protocol):
    devices: dict[str, Any]
    build_errors: dict[str, Exception]
    connection_errors: dict[str, Exception]


@runtime_checkable
class DeviceBuildResult(Protocol):
    devices: dict[str, Any]
    errors: dict[str, Exception]

    def connect(self, timeout: float) -> DeviceConnectResult: ...


@runtime_checkable
class DeviceManager(Protocol):
    def build_and_connect(
        self,
        *,
        mock: bool = False,
        timeout: float | None = None,
        fixtures: dict[str, Any] | None = None,
    ) -> DeviceConnectResult: ...
