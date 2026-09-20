import asyncio
import json

from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponsesAgentServerHost,
    TextResponse,
)
from azure.ai.agentserver.responses.models import get_input_expanded
from opentelemetry import trace
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from telemetry import configure_otel

configure_otel("event-companion-agent")

from agent_runner import run_agent  # noqa: E402

app = ResponsesAgentServerHost(configure_observability=None, access_log=None)
app.add_middleware(OpenTelemetryMiddleware)
tracer = trace.get_tracer("event-companion-agent")


def input_text(request: CreateResponse) -> str:
    value = request.get("input")
    if isinstance(value, str):
        return value
    parts = [
        content["text"]
        for item in get_input_expanded(request)
        if item.get("role") == "user"
        for content in item.get("content", [])
        if content.get("type") == "input_text"
    ]
    return "\n".join(parts)


@app.response_handler
async def handler(
    request: CreateResponse, context: ResponseContext, cancellation_signal: asyncio.Event
):
    message = input_text(request).strip()
    if not message or len(message) > 1000:
        raise ValueError("Expected an event question of 1-1000 characters.")
    with tracer.start_as_current_span("conversation_turn") as span:
        span.set_attribute("gen_ai.operation.name", "invoke_agent")
        operation = asyncio.create_task(run_agent(message))
        cancellation = asyncio.create_task(cancellation_signal.wait())
        shutdown = asyncio.create_task(context.shutdown.wait())
        try:
            async with asyncio.timeout(55):
                completed, _ = await asyncio.wait(
                    {operation, cancellation, shutdown}, return_when=asyncio.FIRST_COMPLETED
                )
                if operation not in completed:
                    raise asyncio.CancelledError
                answer = await operation
                return TextResponse(context, request, text=json.dumps(answer))
        finally:
            for task in (operation, cancellation, shutdown):
                if not task.done():
                    task.cancel()
            await asyncio.gather(operation, cancellation, shutdown, return_exceptions=True)


if __name__ == "__main__":
    app.run(port=8088)
