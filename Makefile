.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help install lint test fmt cluster-up cluster-down observability target-app chaos-install scenario-pod-crash dev-up dev-down

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

dev-up: ## Full local bring-up: cluster, target app, observability, chaos
	bash scripts/dev-up.sh all

dev-down: ## Tear everything down
	bash scripts/dev-down.sh
