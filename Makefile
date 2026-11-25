.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help install lint test fmt cluster-up cluster-down observability target-app chaos-install scenario-pod-crash scenario-cpu-stress eda progress rcaeval-official n1-report n3-smoke data planner-eval web demo prototype prototype-pod-crash prototype-feedback prototype-ui dev-up dev-down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Create the uv environment and sync all workspace members
	uv sync --dev

lint: ## Run ruff + mypy
	uv run ruff check .
	uv run mypy libs services

fmt: ## Auto-format / fix lint
	uv run ruff format .
	uv run ruff check --fix .

test: ## Run the unit test suite
	uv run pytest

cluster-up: ## Create the local kind cluster
	kind create cluster --config deploy/kind/kind-cluster.yaml

cluster-down: ## Delete the local kind cluster
	kind delete cluster --name copilot

target-app: ## Deploy the Online Boutique target application
	kubectl apply -k deploy/target-app/online-boutique

observability: ## Deploy Prometheus + Alertmanager (+ log stack)
	bash scripts/dev-up.sh observability

chaos-install: ## Install Chaos Mesh into the cluster
	bash deploy/chaos-mesh/install.sh

scenario-pod-crash: ## Inject the pod-crash fault scenario (S1)
	uv run python -m scenarios.runner.run pod-crash

scenario-cpu-stress: ## Inject the cpu-stress fault scenario (S2)
	uv run python -m scenarios.runner.run cpu-stress

eda: ## Run RCAEval RE2-OB exploratory data analysis (X0)
	uv run python -m eval.eda_re2ob

rcaeval-all: ## Full RCAEval track on RE2-OB only
	uv run python -m eval.rcaeval.run_all --suite re2ob

rcaeval-everything: ## All RCAEval suites RE1/RE2/RE3 (OB+SS+TT)
	uv run python -m eval.rcaeval.run_all_suites

rcaeval-metrics-validation: ## BARO+NSigma+EDiag, bootstrap CIs, revised targets, study size
	uv run python -m eval.rcaeval.metrics_validation --suite re2ob

RCAEVAL_REPO ?= ../external/RCAEval

rcaeval-official: ## N1: official RCAEval main.py for all baselines on RE2-OB (+RCD), with provenance
	uv run python scripts/reproduce_rcaeval.py --repo "$(RCAEVAL_REPO)" --dataset re2-ob \
	  --python "$(RCAEVAL_REPO)/env/bin/python" \
	  --rcd-python "$(RCAEVAL_REPO)/env-rcd/bin/python" --rcd-methods rcd
	uv run python scripts/run_pdiagnose.py

n1-report: ## N1: one table (AC@1/3/5, Avg@5, 95% CIs, per fault) + redis hypothesis
	uv run python -m eval.rcaeval.redis_hypothesis
	uv run python -m eval.rcaeval.n1_report

n3-smoke: ## N3: Qwen3-4B (MLX) + qwen2.5-7b (Ollama) on RE2-OB, scored by RCAEval's evaluator
	bash scripts/run_n3_mac.sh

data: ## Download the 90 RE2-OB cases into ../datasets/RCAEval (public RCAEval benchmark, ~1 GB)
	uv run --with huggingface_hub python scripts/fetch_re2ob.py

planner-eval: ## Planner experiment on the 30 agent diagnoses (target, fault family, feedback loop)
	uv run python -m eval.planner_eval

web: ## Incident Copilot website: real incident -> LLM RCA -> plan -> approval -> dry-run (http://127.0.0.1:8090)
	uv run uvicorn console.web_app:app --host 127.0.0.1 --port 8090

demo: web ## Alias for `make web`

prototype: ## Early prototype CLI: cpu fault -> correlate -> RCA -> plan -> approve -> dry-run
	uv run python -m console.cli.prototype --scenario cpu-stress --pretty

prototype-pod-crash: ## Early prototype CLI on the pod-crash scenario
	uv run python -m console.cli.prototype --scenario pod-crash --pretty

prototype-feedback: ## Early prototype CLI showing the failed-remedy feedback loop
	uv run python -m console.cli.prototype --scenario cpu-stress --feedback-loop --pretty

prototype-ui: ## Early prototype Streamlit UI (http://localhost:8501)
	uv run streamlit run console/streamlit_app.py --server.headless true

rcaeval-smoke: ## Fast smoke (first 6 cases, skip BARO)
	uv run python -m eval.rcaeval.run_all --suite re2ob --limit 6 --skip-baro

progress: ## Print Workbook 1/2 progress checklist
	@cat docs/PROGRESS.md

dev-up: ## Full local bring-up: cluster, target app, observability, chaos
	bash scripts/dev-up.sh all

dev-down: ## Tear everything down
	bash scripts/dev-down.sh
