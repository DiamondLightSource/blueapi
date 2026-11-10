import logging

from .model import DeviceModel, PlanModel

LOGGER = logging.getLogger(__name__)

__all__ = ["PlanModel", "DeviceModel", "SessionManager"]


def __getattr__(name: str):
    # Backwards compatible alias: SessionManager now lives in blueapi.client.session.
    # Imported lazily as blueapi.client.session itself imports blueapi.service.model.
    if name == "SessionManager":
        from blueapi.client.session import SessionManager

        LOGGER.warning(
            "Importing SessionManager from blueapi.service is deprecated, import it "
            "from blueapi.client.session instead. The old import will be removed in "
            "2 releases of blueapi or 6 months (May 2027)."
        )
        return SessionManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
