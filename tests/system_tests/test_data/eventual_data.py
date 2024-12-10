import time
from contextlib import contextmanager
from pathlib import Path

import h5py as h5

# Currently the nexus writer has no way of letting us know when it is done with a file.
# This repeated try will have to do.


@contextmanager
def hdf5_file_with_backoff(
    path: Path,
    max_attempts: int = 5,
    interval: float = 0.5,
):
    f = _open_file_with_backoff(
        path,
        max_attempts,
        interval,
    )
    try:
        yield f
    finally:
        f.close()


def _open_file_with_backoff(
    path: Path,
    max_attempts: int = 5,
    interval: float = 0.5,
) -> h5.File:
    while max_attempts > 0:
        try:
            return h5.File(str(path))
        except BlockingIOError as ex:
            if max_attempts > 1:
                max_attempts -= 1
                time.sleep(0.5)
            else:
                raise ex
    raise Exception("Failed to open file")
