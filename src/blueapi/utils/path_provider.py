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
        """
        if not self._docs:
            raise BlueskyRunStructureError(
                "Start document not found. This call must be made inside a run."
            )
        else:
            template = self._docs[-1].get("detector_file_template")
            if not template:
                raise ValueError("detector_file_template must be set in metadata")
            sub_path = template.format_map(
                self._docs[-1] | {"device_name": device_name}
            )
            data_session_directory = Path(
                self._docs[-1].get("data_session_directory", "/tmp")
            )
            return PathInfo(directory_path=data_session_directory, filename=sub_path)


class BlueskyRunStructureError(Exception):
    def __init__(self, message):
        super().__init__(message)
