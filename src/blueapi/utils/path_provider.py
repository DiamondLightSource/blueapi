from pathlib import Path

from event_model import RunStart, RunStop
from ophyd_async.core import PathInfo, PathProvider


class StartDocumentPathProvider(PathProvider):
    """A PathProvider that sources from metadata in a RunStart document.

    This uses metadata from a RunStart document to determine file names and
    data session directories. A template can be included in the StartDocument
    to allow for custom naming conventions.

    """

    def __init__(self) -> None:
        self._docs: list[RunStart] = []

    def run_start(self, name: str, start_document: RunStart) -> None:
        if name == "start":
            self._docs.append(start_document)

    def run_stop(self, name: str, stop_document: RunStop) -> None:
        if name == "stop":
            if stop_document.get("run_start") == self._docs[-1]["uid"]:
                self._docs.pop()
            else:
                raise BlueskyRunStructureError(
                    "Close run called, but not for the inner most run. "
                    "This is not supported. If you need to do this speak to core DAQ."
                )

    def __call__(self, device_name: str | None = None) -> PathInfo:
        """Returns the directory path and filename for a given data_session.

        The default template for file naming is: "{instrument}-{scan_id}-{device_name}"
        however, this can be changed by providing a template in the start document. For
        example: "detector_file_template": "custom-{device_name}-{scan_id}".

        If you do not provide a data_session_directory it will default to "/tmp".

        If the start document has a scan_file in a subdirectory of the data session
        directory (e.g. "sample1/ixx-1234"), detector files are written alongside it
        in that subdirectory, which is created if it does not exist.
        """
        if not self._docs:
            raise BlueskyRunStructureError(
                "Start document not found. This call must be made inside a run."
            )
        else:
            doc = self._docs[-1]
            template = doc.get("detector_file_template")
            if not template:
                raise ValueError("detector_file_template must be set in metadata")
            sub_path = template.format_map(doc | {"device_name": device_name})
            data_session_directory = Path(doc.get("data_session_directory", "/tmp"))
            # numtracker's scan_file is relative to data_session_directory, write
            # detector files in the same directory as it ("." if there is no
            # scan_file or it has no subdirectory)
            scan_file_directory = Path(doc.get("scan_file", "")).parent
            return PathInfo(
                directory_path=data_session_directory / scan_file_directory,
                filename=sub_path,
                # Negative depth creates only the directories scan_file adds
                create_dir_depth=-len(scan_file_directory.parts),
            )


class BlueskyRunStructureError(Exception):
    def __init__(self, message):
        super().__init__(message)
