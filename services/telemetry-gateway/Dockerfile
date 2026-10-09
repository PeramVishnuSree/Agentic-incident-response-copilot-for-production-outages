FROM python:3.11-slim

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Workspace build context is the repo root.
COPY pyproject.toml uv.lock* ./
COPY libs/common ./libs/common
COPY services/telemetry-gateway ./services/telemetry-gateway

RUN uv sync --package telemetry-gateway --no-dev

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "telemetry_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
