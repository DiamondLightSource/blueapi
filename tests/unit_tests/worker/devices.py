# Devices to use for worker tests

from bluesky.protocols import Movable
from ophyd import Device, DeviceStatus
from ophyd.status import Status


class AdditionalUpdateStatus(DeviceStatus):
    """
    Status which emits an additional update to watchers
    after the status is finished.
    """

    def add_callback(self, callback):
        retval = super().add_callback(callback)
        return retval

    def watch(self, func):
        """
        set_finished called here instead of add_callback
        to prevent race conditions
        """
        self.set_finished()
        return super().watch(func)

    def _run_callbacks(self) -> None:
        super()._run_callbacks()
        for watcher in self._watchers:
            watcher(
                name="STATUS_AFTER_FINISH",
                current=0.0,
                initial=1.0,
                target=2.0,
                unit="kg",
                precision=0,
                fraction=0.5,
                time_elapsed=1.0,
                time_remaining=1.0,
            )


class AdditionalStatusDevice(Device, Movable):
    def set(self, value: float) -> Status:  # type: ignore
        status = AdditionalUpdateStatus(self)
        return status  # type: ignore


def additional_status_device(name="additional_status_device") -> AdditionalStatusDevice:
    return AdditionalStatusDevice(name=name)
