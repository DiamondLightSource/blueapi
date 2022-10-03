import socket
from typing import Any, Dict

from ophyd import Component as Cpt
from ophyd import DetectorBase, EpicsMotor, MotorBundle, SingleTrigger
from ophyd.areadetector.cam import AreaDetectorCam
from ophyd.areadetector.filestore_mixins import FileStoreHDF5, FileStoreIterativeWrite
from ophyd.areadetector.plugins import HDF5Plugin, PosPlugin, StatsPlugin

from blueapi.plans import *  # noqa: F403

HOSTNAME = socket.gethostname().split(".")[0]
DATA_ROOT: str = "/tmp"
DATA_WRITE_PATH_TEMPLATE: str = "%Y"


class AdSimDetector(SingleTrigger, DetectorBase):
    class HDF5File(HDF5Plugin, FileStoreHDF5, FileStoreIterativeWrite):
        pool_max_buffers = None
        file_number_sync = None
        file_number_write = None

        def get_frames_per_point(self):
            return self.parent.cam.num_images.get()

    cam: AreaDetectorCam = Cpt(AreaDetectorCam, suffix="CAM:")
    stat: StatsPlugin = Cpt(StatsPlugin, suffix="STAT:")
    pos: PosPlugin = Cpt(PosPlugin, suffix="POS:")
    hdf: HDF5File = Cpt(
        HDF5File,
        suffix="HDF5:",
        root=DATA_ROOT,
        write_path_template=DATA_WRITE_PATH_TEMPLATE,
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.hdf.kind = "normal"

        # These signals will be set to their consituent values
        # when stage() is called and returned to their original
        # values when unstage() is called
        self.stage_sigs = {
            # Setup the plugin chain
            self.stat.nd_array_port: self.cam.port_name.get(),
            self.hdf.nd_array_port: self.cam.port_name.get(),
            # Setup Driver
            self.cam.array_counter: 0,
            self.cam.image_mode: "Multiple",
            self.cam.trigger_mode: "Internal",
            # Calculate stats
            self.stat.compute_centroid: 1,
            # Any preexisting config
            **self.stage_sigs,  # type: ignore
        }

        self.read_attrs += ["stat"]
        self.stat.read_attrs += ["total", "centroid"]
        self.stat.centroid.read_attrs += ["x", "y"]

    @property
    def hints(self) -> Dict[str, Any]:
        return {"fields": ["stat.total"]}


class SimBundle(MotorBundle):
    """
    ADSIM EPICS motors
    """

    x: EpicsMotor = Cpt(EpicsMotor, "M1")
    y: EpicsMotor = Cpt(EpicsMotor, "M2")
    z: EpicsMotor = Cpt(EpicsMotor, "M3")
    theta: EpicsMotor = Cpt(EpicsMotor, "M4")
    load: EpicsMotor = Cpt(EpicsMotor, "M5")


motors = SimBundle(name="motors", prefix=f"{HOSTNAME}-MO-SIM-01:")
motors.wait_for_connection()
det = AdSimDetector(name="adsim", prefix=f"{HOSTNAME}-AD-SIM-01:")
det.wait_for_connection()

__all__ = [  # noqa: F405
    "motors",
    "det",
    "set_absolute",
    "set_relative",
    "move",
    "move_relative",
    "sleep",
    "wait",
    "scan",
    "count",
]
