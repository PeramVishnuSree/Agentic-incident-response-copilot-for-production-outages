FROM python:3.12-slim

RUN pip install --no-cache-dir uv && useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    UV_PROJECT_ENVIRONMENT=/home/user/venv \
    PATH=/home/user/venv/bin:$PATH \
    RCAEVAL_DIR=/home/user/data/RCAEval \
    COPILOT_HOSTED=1
WORKDIR /home/user/app

COPY --chown=user . .
RUN uv sync --frozen --no-dev \
 && uv pip install --python /home/user/venv/bin/python \
      "fastapi>=0.115" "uvicorn>=0.30" "pyyaml>=6.0" "pandas>=2.2" "pyarrow>=15" "huggingface_hub>=0.24"
RUN python scripts/fetch_re2ob.py --demo-only --dest "$RCAEVAL_DIR"

EXPOSE 7860
CMD ["uvicorn", "console.web_app:app", "--host", "0.0.0.0", "--port", "7860"]
