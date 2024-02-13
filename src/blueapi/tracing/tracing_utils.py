import typing

from fastapi import FastAPI
from opentelemetry.context import Context, get_current  # type: ignore
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # type: ignore
from opentelemetry.propagate import get_global_textmap  # type: ignore
from opentelemetry.sdk.resources import Resource  # type: ignore
from opentelemetry.sdk.trace import TracerProvider  # type: ignore
from opentelemetry.sdk.trace.export import (  # type: ignore
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.trace import (  # type: ignore
    Tracer,
    get_current_span,
    get_tracer_provider,
    set_tracer_provider,
)
from stomp.utils import Frame

PROPAGATOR = get_global_textmap()


def instrument_fastapi_app(app: FastAPI, name: str) -> None:
    """Sets up automated Open Telemetry for a FastAPI app. This should be called in the
    main module of the app to establish the global TracerProvider and the name of the
    service that the generated traces belong to. A SpanProcessor that will export its
    trace information using the OTLP Open Telemetry protocol is then added. The
    instrumentor is then invoked to instrument the FastAPI call handlers. Thereafter,
    Other files can use the get_tracer_provider call to hook in to the apps OTEL
    infrastructure when creating new SpanProcessors or setting up manual Span
    generation."""
    resource = Resource(attributes={"service.name": name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    set_tracer_provider(provider)
    FastAPIInstrumentor().instrument_app(app)


def set_console_exporter() -> None:
    resource = Resource(attributes={"service.name": "BlueAPI"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))


def get_tracer(name: str) -> Tracer:
    """A wrapper around the library function to establish the recommended naming
    convention for a module's Tracer"""
    name = "opentelemetry.instrumentation." + name
    return get_tracer_provider().get_tracer(name)


def add_trace_attributes(attributes: dict) -> None:
    if attributes is None:
        attributes = {}
    sp = get_current_span()
    sc = sp.get_span_context()
    attributes["TraceId"] = hex(sc.trace_id)
    attributes["SpanId"] = hex(sc.span_id)
    sp.set_attributes(attributes)


def get_header_from_frame(frame: Frame, key: str) -> list:
    """Handler function for use by PROPAGATOR.extract"""
    return [frame.headers.get(key)]


def propagate_context_in_headers(
    headers: dict[str, typing.Any], context: typing.Optional[Context] = None
) -> None:
    PROPAGATOR.inject(headers, context)


def retrieve_context_from_headers(frame: Frame) -> Context:
    return PROPAGATOR.extract(carrier=frame.headers)


def get_trace_context() -> Context:
    """Somewhat redundant but the fn name "get_current" is rather ambiguous."""
    return get_current()
