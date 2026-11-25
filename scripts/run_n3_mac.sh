#!/usr/bin/env bash
# N3 on Apple Silicon: real open-weight models, real RE2-OB cases, no GPU cluster needed.
#
# Needs, in other terminals:
#   mlx_lm.server --model mlx-community/Qwen3-4B-4bit --host 127.0.0.1 --port 8080
#   ollama serve            # with: ollama pull qwen2.5:7b-instruct   (optional comparison)
# Optional, for scoring with RCAEval's own evaluator:
#   RCAEVAL_REPO pointing at an RCAEval checkout with `rcaeval-agent export --dataset re2-ob`
#   already run into $RCAEVAL_REPO/agent_tasks.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
CASES_DIR="${RCAEVAL_DIR:-$ROOT/datasets/RCAEval}/RE2-OB"
RCAEVAL_REPO="${RCAEVAL_REPO:-$ROOT/../external/RCAEval}"
MLX_URL="${MLX_URL:-http://127.0.0.1:8080/v1}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434/v1}"
ALL30="$(ls "$CASES_DIR" | grep '_1$' | paste -sd, -)"
smoke() { uv run python experiments/n3/run_smoke_test.py "$CASES_DIR" "$@"; }

smoke --prompt v1 --base-url "$MLX_URL" --model mlx-community/Qwen3-4B-4bit
smoke --prompt v2 --base-url "$MLX_URL" --model mlx-community/Qwen3-4B-4bit
smoke --prompt v2 --base-url "$MLX_URL" --model mlx-community/Qwen3-4B-4bit \
  --cases "$ALL30" --label extended30_Qwen3-4B-4bit_prompt-v2
if curl -sf "$OLLAMA_URL/models" > /dev/null; then
  smoke --prompt v2 --base-url "$OLLAMA_URL" --model qwen2.5:7b-instruct
fi

if [ -x "$RCAEVAL_REPO/env/bin/rcaeval-agent" ] && [ -d "$RCAEVAL_REPO/agent_tasks/re2-ob" ]; then
  for run in experiments/n3/trajectories/*/; do
    uv run python experiments/n3/score_with_rcaeval.py "$run" \
      --tasks "$RCAEVAL_REPO/agent_tasks/re2-ob" \
      --rcaeval-agent "$RCAEVAL_REPO/env/bin/rcaeval-agent" | grep "Predicted cases only"
  done
fi
