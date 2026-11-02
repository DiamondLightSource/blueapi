from .model import DeviceModel, PlanModel

__all__ = ["PlanModel", "DeviceModel", "SessionManager"]


def __getattr__(name: str):
    # Backwards compatible alias: SessionManager now lives in blueapi.client.session.
    # Imported lazily as blueapi.client.session itself imports blueapi.service.model.
    if name == "SessionManager":
        from blueapi.client.session import SessionManager

        return SessionManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
