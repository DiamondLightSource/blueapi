"""Timestamps of the i08-1 Andor config PVs that end up in the descriptor.

Not run in CI (ignored by the system-test tox env). Mocked by default,
set I08_1_MOCK=0 on a machine that can see BL08J-EA-DET-08 to read the real IOC.
"""

import os
from datetime import UTC, datetime

import pytest
from ophyd_async.epics.core import epics_signal_r

PREFIX = "BL08J-EA-DET-08:CAM:"
# EPICS epoch (1990-01-01 UTC): what a record that has never processed reports
EPICS_EPOCH = 631152000.0
MOCK = os.environ.get("I08_1_MOCK", "1") == "1"


@pytest.fixture
async def readings() -> dict:
    out = {}
    for pv in ("AcquireTime_RBV", "AcquirePeriod_RBV"):
        signal = epics_signal_r(float, f"ca://{PREFIX}{pv}", name=pv)
        await signal.connect(mock=MOCK)
        out.update(await signal.read())
    return out


def test_print_andor_timestamps(readings: dict):
    for name, reading in readings.items():
        ts = reading["timestamp"]
        print(f"{name}: {ts} = {datetime.fromtimestamp(ts, UTC).isoformat()}")


def test_andor_timestamps_are_utc_now_not_epics_epoch(readings: dict):
    for name, reading in readings.items():
        assert reading["timestamp"] > EPICS_EPOCH, (
            f"{name} timestamp is the EPICS epoch, the record never processed"
        )
