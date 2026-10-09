#!/usr/bin/env bash
# Install Chaos Mesh into the kind cluster (S1 — Peram).
# Fallback: if Chaos Mesh is unavailable, scenarios can inject faults with
# scripted kubectl + stress tools instead (see workbook §4.1).
set -euo pipefail

helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update

helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh \
  -n chaos-mesh --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock

echo "Chaos Mesh installed. Dashboard: kubectl -n chaos-mesh port-forward svc/chaos-dashboard 2333:2333"
