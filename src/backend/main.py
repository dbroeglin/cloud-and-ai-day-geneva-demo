from event_companion.app import create_app
from telemetry import configure_otel

configure_otel("event-companion-backend")
app = create_app()

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: E402
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor  # noqa: E402

FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()
