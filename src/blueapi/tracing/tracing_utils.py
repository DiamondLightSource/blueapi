import typing

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Tracer, get_tracer_provider, set_tracer_provider, get_current_span
from opentelemetry.propagate import get_global_textmap
from opentelemetry.context import Context, get_current
from stomp.utils import Frame


PROPAGATOR = get_global_textmap()


def instrument_fastapi_app(app: FastAPI, name: str) -> None:
    ''' Sets up automated Open Telemetry for a FastAPI app. This should be called in the main
        module of the app to establish the global TracerProvider and the name of the service
        that the generated traces belong to. A SpanProcessor that will export its trace 
        information using the OTLP Open Telemetry protocol is then added. The instrumentor 
        is then invoked to instrument the FastAPI call handlers. Thereafter, Other files can 
        use the get_tracer_provider call to hook in to the apps OTEL infrastructure when creating 
        new SpanProcessors or setting up manual Span generation. '''
    resource = Resource(attributes={"service.name": name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    set_tracer_provider(provider)
    FastAPIInstrumentor().instrument_app(app)


def get_tracer(name: str) -> Tracer:
    ''' A wrapper around the library function to establish the recommended naming convention
        for a module's Tracer'''
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


def get_header_from_frame(frame: Frame, key: str) -> dict:
    ''' Handler function for use by PROPAGATOR.extract '''
    return frame.headers.get(key)


def propagate_context_in_headers(
    headers: dict[str, typing.Any], context: Context = get_current()
) -> None:
    PROPAGATOR.inject(headers, context)


def retrieve_context_from_headers(frame: Frame) -> Context:
    return PROPAGATOR.extract(get_header_from_frame, frame)


def get_trace_context() -> Context:
    ''' Somewhat redundant but the fn name "get_current" is rather ambiguous. '''
    return get_current()
