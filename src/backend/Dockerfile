FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY event_companion/ /app/event_companion/
COPY main.py telemetry.py /app/
RUN useradd --uid 10001 --create-home app
USER app
ENV APP_ENV=azure PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
