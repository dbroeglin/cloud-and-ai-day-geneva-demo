FROM python:3.14-slim
WORKDIR /app
COPY src/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY src/backend/ /app/
COPY src/agents/event-guide/telemetry.py /app/telemetry.py
RUN useradd --uid 10001 --create-home app
USER app
ENV APP_ENV=azure PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
