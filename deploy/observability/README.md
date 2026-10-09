# Observability stack (S1 — Gandham)

Provides the telemetry the copilot diagnoses over. Install via Helm:

```bash
# Metrics + alerts
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install kube-prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f deploy/observability/prometheus/values.yaml

# Logs (S2): Fluent Bit -> Elasticsearch.
# Fallback: switch to Loki if cluster memory is insufficient (see workbook §4.1).
```

Prometheus is exposed on host port 9090 and Alertmanager on 9093 (see
`deploy/kind/kind-cluster.yaml`). Alert rules that feed the incident store live
in `prometheus/alert-rules.yaml`.
