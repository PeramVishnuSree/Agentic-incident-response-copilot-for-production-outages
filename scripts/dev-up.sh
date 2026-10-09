#!/usr/bin/env bash
# Local testbed bring-up. Usage: scripts/dev-up.sh [all|cluster|target|observability|chaos]
set -euo pipefail
cd "$(dirname "$0")/.."

step="${1:-all}"

cluster() {
  kind get clusters | grep -qx copilot || kind create cluster --config deploy/kind/kind-cluster.yaml
}
target() { kubectl apply -k deploy/target-app/online-boutique; }
observability() {
  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
  helm repo update
  helm upgrade --install kube-prometheus prometheus-community/kube-prometheus-stack \
    -n monitoring --create-namespace -f deploy/observability/prometheus/values.yaml
}
chaos() { bash deploy/chaos-mesh/install.sh; }

case "$step" in
  cluster) cluster ;;
  target) target ;;
  observability) observability ;;
  chaos) chaos ;;
  all) cluster; target; observability; chaos ;;
  *) echo "unknown step: $step" >&2; exit 2 ;;
esac
echo "dev-up '$step' complete."
