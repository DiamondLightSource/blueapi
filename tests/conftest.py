import asyncio
from typing import cast

# Based on https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tests-according-to-command-line-option  # noqa: E501
import pytest
from bluesky import RunEngine
from bluesky.run_engine import TransitionError
from observability_utils.tracing import JsonObjectSpanExporter, setup_tracing
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import get_tracer_provider


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


@pytest.fixture(scope="session")
def exporter() -> TracerProvider:
    setup_tracing("test", False)
    exporter = JsonObjectSpanExporter()
    provider = cast(TracerProvider, get_tracer_provider())
    # Use SimpleSpanProcessor to keep tests quick
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter
