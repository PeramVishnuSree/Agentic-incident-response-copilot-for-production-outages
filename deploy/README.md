# Deployment (testbed)

Bring-up order for the local testbed (S1). See `../scripts/dev-up.sh` for the
scripted version and the top-level `Makefile` for shortcuts.

1. **Cluster** — `make cluster-up` (kind, 1 control-plane + 2 workers).
2. **Target app** — `make target-app` (Online Boutique in `online-boutique`).
3. **Observability** — `make observability` (Prometheus + Alertmanager; Grafana on).
4. **Chaos Mesh** — `make chaos-install` (fault-injection controller).
5. **First scenario** — `make scenario-pod-crash` (inject + record ground truth).

| Path | Owner | Purpose |
|------|-------|---------|
| `kind/` | Gandham | Local Kubernetes cluster definition |
| `target-app/online-boutique/` | Gandham | Realistic microservice workload |
| `observability/` | Gandham | Metrics, alerts, logs stack |
| `chaos-mesh/` | Peram | Fault-injection controller |
| `helm/` (S4) | Gandham | Umbrella chart for the copilot services |
