FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir .
COPY bridge /app/bridge

CMD ["uvicorn", "bridge.main:app", "--host", "0.0.0.0", "--port", "8080"]

