FROM python:3.11-slim

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Workspace build context is the repo root.
COPY pyproject.toml uv.lock* ./
COPY libs/common ./libs/common
COPY services/rca-agent ./services/rca-agent

RUN uv sync --package rca-agent --no-dev

CMD ["uv", "run", "python", "-c", "import rca_agent; print('rca-agent image ok')"]
