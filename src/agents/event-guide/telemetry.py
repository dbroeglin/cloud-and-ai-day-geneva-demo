import gzip
import logging
import os
import re
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry.exporter import (
    AzureMonitorLogExporter,
    AzureMonitorMetricExporter,
    AzureMonitorTraceExporter,
)
from copilot import TelemetryConfig
from opentelemetry import _logs, metrics, trace
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import SpanContext, SpanKind, Status, StatusCode, TraceFlags

SAFE_KEYS = {
    "http.method",
    "http.request.method",
    "http.route",
    "http.status_code",
    "http.response.status_code",
    "server.address",
    "server.port",
    "url.scheme",
    "gen_ai.operation.name",
    "gen_ai.provider.name",
    "gen_ai.request.model",
    "gen_ai.response.model",
    "gen_ai.tool.name",
    "gen_ai.tool.type",
    "event.source_count",
    "event.refused",
    "error.type",
}
GUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
_exporter: SpanExporter | None = None
_credential: DefaultAzureCredential | None = None
_relay: ThreadingHTTPServer | None = None


def safe_attributes(attributes) -> dict:
    result = {}
    for key, value in (attributes or {}).items():
        if key in SAFE_KEYS or key.startswith("gen_ai.usage."):
            result[key] = GUID.sub("{id}", value[:1000]) if isinstance(value, str) else value
        elif key.startswith("event.public.") and os.getenv("ENABLE_SENSITIVE_DATA") == "true":
            result[key] = str(value)[:8192]
    return result


class RedactingExporter(SpanExporter):
    def __init__(self, inner: SpanExporter):
        self.inner = inner

    def export(self, spans) -> SpanExportResult:
        clean = [
            ReadableSpan(
                name=GUID.sub("{id}", span.name.split("?")[0])[:200],
                context=span.context,
                parent=span.parent,
                resource=span.resource,
                attributes=safe_attributes(span.attributes),
                events=(),
                links=span.links,
                kind=span.kind,
                status=Status(span.status.status_code),
                start_time=span.start_time,
                end_time=span.end_time,
                instrumentation_scope=span.instrumentation_scope,
            )
            for span in spans
        ]
        return self.inner.export(clean)

    def shutdown(self) -> None:
        self.inner.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.inner.force_flush(timeout_millis)


def configure_otel(service_name: str) -> None:
    global _exporter, _credential
    os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "false"
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    connection = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection:
        if os.getenv("APP_ENV") == "azure":
            raise RuntimeError("Application Insights routing configuration is required in Azure.")
        logging.getLogger(__name__).info(
            "Local telemetry export is disabled (no Insights configured)."
        )
        return
    _credential = DefaultAzureCredential()
    options = {
        "connection_string": connection,
        "credential": _credential,
        "storage_directory": os.path.join(tempfile.gettempdir(), "event-companion-telemetry"),
    }
    resource = Resource.create({"service.name": service_name, "service.version": "0.1.0"})
    _exporter = RedactingExporter(AzureMonitorTraceExporter(**options))
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(_exporter))
    trace.set_tracer_provider(provider)
    metrics.set_meter_provider(
        MeterProvider(
            resource=resource,
            metric_readers=[
                PeriodicExportingMetricReader(
                    AzureMonitorMetricExporter(**options), export_interval_millis=10000
                )
            ],
        )
    )
    logs = LoggerProvider(resource=resource)
    logs.add_log_record_processor(BatchLogRecordProcessor(AzureMonitorLogExporter(**options)))
    _logs.set_logger_provider(logs)
    handler = LoggingHandler(level=logging.INFO, logger_provider=logs)
    handler.addFilter(
        lambda record: record.name.startswith(("event_companion", "agent_runner", "telemetry"))
    )
    logging.getLogger().addHandler(handler)
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _attribute_value(value):
    kind = value.WhichOneof("value")
    if kind in ("string_value", "bool_value", "int_value", "double_value"):
        return getattr(value, kind)
    return None


def decode_spans(data: bytes) -> list[ReadableSpan]:
    message = ExportTraceServiceRequest.FromString(data)
    spans = []
    for resource_spans in message.resource_spans:
        resource = Resource.create({"service.name": "event-companion-agent-cli"})
        for scope_spans in resource_spans.scope_spans:
            for span in scope_spans.spans:
                context = SpanContext(
                    int.from_bytes(span.trace_id),
                    int.from_bytes(span.span_id),
                    is_remote=False,
                    trace_flags=TraceFlags(span.flags & 0xFF),
                )
                parent = (
                    SpanContext(context.trace_id, int.from_bytes(span.parent_span_id), False)
                    if span.parent_span_id
                    else None
                )
                attributes = {
                    attr.key: parsed
                    for attr in span.attributes
                    if (parsed := _attribute_value(attr.value)) is not None
                }
                spans.append(
                    ReadableSpan(
                        name=span.name,
                        context=context,
                        parent=parent,
                        resource=resource,
                        attributes=attributes,
                        kind=SpanKind(span.kind - 1) if 1 <= span.kind <= 5 else SpanKind.INTERNAL,
                        status=Status(
                            {0: StatusCode.UNSET, 1: StatusCode.OK, 2: StatusCode.ERROR}[
                                span.status.code
                            ]
                        ),
                        start_time=span.start_time_unix_nano,
                        end_time=span.end_time_unix_nano,
                    )
                )
    return spans


class RelayHandler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        pass

    def do_POST(self):  # noqa: N802
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400)
            return
        if size < 0 or size > 1048576:
            self.send_error(413)
            return
        data = self.rfile.read(size)
        if self.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        if len(data) > 4194304:
            self.send_error(413)
            return
        if self.path == "/v1/traces":
            spans = decode_spans(data)
            if _exporter is None or _exporter.export(spans) != SpanExportResult.SUCCESS:
                self.send_error(503)
                return
        elif self.path != "/v1/metrics":
            self.send_error(404)
            return
        # Token metrics are exported from typed SDK usage events, not duplicated from OTLP.
        self.send_response(200)
        self.send_header("Content-Type", "application/x-protobuf")
        self.send_header("Content-Length", "0")
        self.end_headers()


def _copilot_telemetry() -> TelemetryConfig | None:
    global _relay
    if _exporter is None:
        return None
    if _relay is None:
        _relay = ThreadingHTTPServer(("127.0.0.1", 0), RelayHandler)
        threading.Thread(
            target=_relay.serve_forever, daemon=True, name="copilot-otel-relay"
        ).start()
    return {
        "otlp_endpoint": f"http://127.0.0.1:{_relay.server_port}",
        "otlp_protocol": "http/protobuf",
        "exporter_type": "otlp-http",
        "source_name": "event-companion-agent-cli",
        "capture_content": False,
    }
