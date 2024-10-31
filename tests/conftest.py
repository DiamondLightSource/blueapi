import asyncio
from typing import cast

# Based on https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tests-according-to-command-line-option  # noqa: E501
import pytest
from bluesky import RunEngine
from bluesky.run_engine import TransitionError
from observability_utils.tracing import setup_tracing
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import get_tracer_provider

from tests.unit_tests.utils.test_tracing import JsonObjectSpanExporter


@pytest.fixture(scope="function")
def RE(request):
    loop = asyncio.new_event_loop()
    loop.set_debug(True)
    RE = RunEngine({}, call_returns_result=True, loop=loop)

    def clean_event_loop():
        if RE.state not in ("idle", "panicked"):
            try:
                RE.halt()
            except TransitionError:
                pass
        loop.call_soon_threadsafe(loop.stop)
        RE._th.join()
        loop.close()

    request.addfinalizer(clean_event_loop)
    return RE


@pytest.fixture
def provider() -> TracerProvider:
    setup_tracing("test", False)
    return cast(TracerProvider, get_tracer_provider())


@pytest.fixture
def exporter(provider: TracerProvider) -> JsonObjectSpanExporter:
    exporter = JsonObjectSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return exporter
