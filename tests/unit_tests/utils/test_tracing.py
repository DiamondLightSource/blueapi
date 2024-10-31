from collections.abc import Callable, Sequence
from concurrent.futures import Future
from contextlib import contextmanager
from typing import IO

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
)


class JsonObjectSpanExporter(SpanExporter):
    """A custom span exporter to allow spans created by open telemetry tracing code to
    be examined and verified during normal testing
    """

    def __init__(
        self,
        service_name: str | None = "Test",
        out: IO | None = None,
        formatter: Callable[[ReadableSpan], str] | None = None,
    ):
        self.service_name = service_name
        self.top_span = Future()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if self.top_span is not None and not self.top_span.done():
            self.top_span.set_result(spans[-1])
        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


@contextmanager
def span_exporter(exporter: JsonObjectSpanExporter, func_name: str, *span_args: str):
    """Use as a with block around the function under test decorated with
    start_as_current_span to check span creation and content.

    params:
        func_name: The name of the function being tested
        span_args: The arguments specified in its start_as_current_span decorator
    """
    # EXPORTER.prime()
    yield
    if exporter.top_span is not None:
        span = exporter.top_span.result(10)
        exporter.top_span = None
        assert span.name == func_name
        for param in span_args:
            assert param in span.attributes.keys()
