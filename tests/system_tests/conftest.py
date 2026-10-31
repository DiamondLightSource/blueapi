import pytest
import requests
from tests.system_tests.stack import services


def _listening(url: str) -> bool:
    try:
        requests.get(url, timeout=5)
    except requests.ConnectionError:
        return False
    except requests.RequestException:
        pass  # Something answered, just slowly
    return True


@pytest.fixture(scope="session", autouse=True)
def system_test_services(request: pytest.FixtureRequest):
    """Start the services unless a blueapi server is already running locally"""
    if _listening("http://localhost:8000/healthz"):
        yield
    elif _listening("http://localhost:8081"):
        raise RuntimeError(
            "Services are running (just services?) but no blueapi server is, "
            "start one with `just serve`"
        )
    else:
        with services() as dump_logs:
            yield
            if request.session.testsfailed:
                dump_logs()
