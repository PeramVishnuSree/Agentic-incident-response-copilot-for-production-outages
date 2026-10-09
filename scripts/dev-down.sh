#!/usr/bin/env bash
# Tear down the local testbed.
set -euo pipefail
cd "$(dirname "$0")/.."

# Best-effort cleanup of the active fault, then delete the cluster.
uv run python -m scenarios.runner.run pod-crash --cleanup || true
kind delete cluster --name copilot
echo "dev-down complete."
