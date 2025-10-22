from pathlib import Path

from event_model import RunStart, RunStop
from ophyd_async.core import PathInfo, PathProvider

DEFAULT_TEMPLATE = "{device_name}-{instrument}-{scan_id}"


class StartDocumentPathProvider(PathProvider):
    """A PathProvider that sources from metadata in a RunStart document.

    This uses metadata from a RunStart document to determine file names and data session
    directories. The file naming defaults to "{device_name}-{instrument}-{scan_id}", so
    the file name is incremented by scan number. A template can be included in the
    StartDocument to allow for custom naming conventions.

    """

    def __init__(self) -> None:
        self._doc: RunStart | None = None

    def run_start(self, name: str, start_document: RunStart) -> None:
        if name == "start" and self._doc is None:
            self._doc = start_document

    def run_stop(self, name: str, stop_document: RunStop) -> None:
        if (
            name == "stop"
            and self._doc is not None
            and stop_document.get("run_start") == self._doc["uid"]
        ):
            self._doc = None

    def __call__(self, device_name: str | None = None) -> PathInfo:
        """Returns the directory path and filename for a given data_session.

        The default template for file naming is: "{device_name}-{instrument}-{scan_id}"
        however, this can be changed by providing a template in the start document. For
        example: "template": "custom-{device_name}--{scan_id}".

        If you do not provide a data_session_directory it will default to "/tmp".
        """
        if self._doc is None:
            raise AttributeError(
                "Start document not found. This call must be made inside a run."
            )
        else:
            template = self._doc.get("data_file_path_template", DEFAULT_TEMPLATE)
            sub_path = template.format_map(self._doc | {"device_name": device_name})
            data_session_directory = Path(
                self._doc.get("data_session_directory", "/tmp")
            )
            return PathInfo(directory_path=data_session_directory, filename=sub_path)
