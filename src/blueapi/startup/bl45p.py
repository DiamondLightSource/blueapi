from nslsii.ad33 import CamV33Mixin, SingleTriggerV33
from ophyd import Component as Cpt
from ophyd import DetectorBase, EpicsMotor, MotorBundle
from ophyd.areadetector.base import ADComponent as Cpt
from ophyd.areadetector.cam import AreaDetectorCam
from ophyd.areadetector.detectors import DetectorBase
from ophyd.areadetector.filestore_mixins import FileStoreHDF5, FileStoreIterativeWrite
from ophyd.areadetector.plugins import HDF5Plugin

from blueapi.plans import *  # noqa: F401, F403


class SampleY(MotorBundle):
    top: EpicsMotor = Cpt(EpicsMotor, "Y:TOP")
    bottom: EpicsMotor = Cpt(EpicsMotor, "Y:BOT")


class SampleTheta(MotorBundle):
    top: EpicsMotor = Cpt(EpicsMotor, "THETA:TOP")
    bottom: EpicsMotor = Cpt(EpicsMotor, "THETA:BOT")


class SampleStage(MotorBundle):
    x: EpicsMotor = Cpt(EpicsMotor, "X")
    y: SampleY = Cpt(SampleY, "")
    theta: SampleTheta = Cpt(SampleTheta, "")


class Choppers(MotorBundle):
    x: EpicsMotor = Cpt(EpicsMotor, "ENDAT")
    y: EpicsMotor = Cpt(EpicsMotor, "BISS")


_ACQUIRE_BUFFER_PERIOD = 0.2


class NonBlockingCam(AreaDetectorCam, CamV33Mixin):
    ...


# define a detector device class that has the correct PV suffixes for the rigs
class GigeCamera(SingleTriggerV33, DetectorBase):
    class HDF5File(HDF5Plugin, FileStoreHDF5, FileStoreIterativeWrite):
        pool_max_buffers = None
        file_number_sync = None
        file_number_write = None

        def get_frames_per_point(self):
            return self.parent.cam.num_images.get()

    cam: NonBlockingCam = Cpt(NonBlockingCam, suffix="DET:")
    hdf: HDF5File = Cpt(
        HDF5File,
        suffix="HDF5:",
        root="/dls/tmp/vid18871/data",
        write_path_template="%Y",
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.hdf.kind = "normal"

        # Get stage to wire up the plugins
        self.stage_sigs[self.hdf.nd_array_port] = self.cam.port_name.get()

        # Makes the detector allow non-blocking AD plugins but makes Ophyd use
        # the AcquireBusy PV to determine when an acquisition is complete
        self.cam.ensure_nonblocking()

        # Reset array counter on stage
        self.stage_sigs[self.cam.array_counter] = 0

        # Set image mode to multiple on stage so we have the option, can still
        # set num_images to 1
        self.stage_sigs[self.cam.image_mode] = "Multiple"

        # For now, this Ophyd device does not support hardware
        # triggered scanning, disable on stage
        self.stage_sigs[self.cam.trigger_mode] = "Off"

    def make_data_key(self):
        source = "PV:{}".format(self.prefix)
        # This shape is expected to match arr.shape for the array.
        shape = (
            self.cam.num_images.get(),
            self.cam.array_size.array_size_y.get(),
            self.cam.array_size.array_size_x.get(),
        )
        return dict(shape=shape, source=source, dtype="array", external="FILESTORE:")

    def stage(self, *args, **kwargs):
        # We have to manually set the acquire period bcause the EPICS driver
        # doesn't do it for us. If acquire time is a staged signal, we use the
        # stage value to calculate the acquire period, otherwise we perform
        # a caget and use the current acquire time.
        if self.cam.acquire_time in self.stage_sigs:
            acquire_time = self.stage_sigs[self.cam.acquire_time]
        else:
            acquire_time = self.cam.acquire_time.get()
        acquire_period = acquire_time + _ACQUIRE_BUFFER_PERIOD
        self.stage_sigs[self.cam.acquire_period] = acquire_period

        # Now calling the super method should set the acquire period
        super(GigeCamera, self).stage(*args, **kwargs)


sample = SampleStage(name="sample", prefix="BL45P-MO-STAGE-01:")
choppers = Choppers(name="chopper", prefix="BL45P-MO-CHOP-01:")
det = GigeCamera(name="det", prefix="BL45P-EA-MAP-01:")
diff = GigeCamera(name="diff", prefix="BL45P-EA-DIFF-01:")

for device in sample, choppers, det, diff:
    device.wait_for_connection()  # type: ignore
